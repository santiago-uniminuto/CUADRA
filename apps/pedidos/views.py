"""Waiter operations. Payment and stock deduction belong to the cashier sprint."""
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.algoritmos.ordenamiento import quick_sort
from apps.auditoria.utils import registrar
from apps.catalogo.models import Producto
from apps.inventario.models import Inventario
from apps.usuarios.decorators import get_sede_efectiva, role_required, get_actuando_como
from apps.usuarios.models import Sede
from .models import DetallePedido, Mesa, Pedido
from .reservas import mensaje_sin_stock, reservas_por_producto


def _integer(value):
    return int(value) if value and value.isascii() and value.isdecimal() and len(value) <= 9 else None


def _assert_owner(request, waiter_id):
    """Admin sin modo actuacion puede intervenir; los meseros no comparten pedidos."""
    if waiter_id != request.user.pk and not (request.user.rol == 'ADMIN' and not get_actuando_como(request)):
        raise PermissionDenied('This table is assigned to another waiter.')


def _assert_table_owner(request, table):
    """Solo el responsable de la atención actual (o admin puro)."""
    if table.responsable_actual_id:
        _assert_owner(request, table.responsable_actual_id)



def _table(request, pk, lock=False):
    qs = Mesa.objects.select_for_update() if lock else Mesa.objects.all()
    return get_object_or_404(qs, pk=pk, sede=get_sede_efectiva(request), activo=True)


@role_required('WAITER')
def tables(request):
    site = get_sede_efectiva(request)
    # Tables are provisioned only if the site has none. Never silently re-enable disabled tables.
    with transaction.atomic():
        if not Mesa.objects.filter(sede=site).exists():
            list(Mesa.objects.bulk_create([Mesa(sede=site, numero=n) for n in range(1, 9)], ignore_conflicts=True))
    items = quick_sort(Mesa.objects.filter(sede=site, activo=True).select_related('responsable_actual'), key=lambda mesa: (mesa.numero, mesa.pk))
    open_orders = {order.mesa_id: order.pk for order in Pedido.objects.filter(mesa__in=items, estado=Pedido.Estado.OPEN)}
    for item in items:
        item.open_order_id = open_orders.get(item.pk)
        item.has_open_order = bool(item.open_order_id)
        owner = item.responsable_actual if item.estado == Mesa.Estado.OCCUPIED else None
        item.owner_name = (owner.nombre or owner.username) if owner else None
        item.is_other_waiter = bool(owner and owner.pk != request.user.pk and
                                    not (request.user.rol == 'ADMIN' and not get_actuando_como(request)))
    return render(request, 'pedidos/tables.html', {'tables': items, 'site': site})


@require_POST
@role_required('WAITER')
def open_order(request, table_id):
    with transaction.atomic():
        table = _table(request, table_id, lock=True)
        _assert_table_owner(request, table)
        if Pedido.objects.filter(mesa=table, estado=Pedido.Estado.OPEN).exists():
            messages.error(request, 'This table already has an open order.')
            return redirect('pedidos:tables')
        table.estado = Mesa.Estado.OCCUPIED
        table.responsable_actual = request.user
        table.save(update_fields=['estado', 'responsable_actual'])
        order = Pedido.objects.create(mesa=table, mesero=request.user)
        registrar(request, 'ORDER_OPEN', 'Pedido', order, f'Opened order for table {table.numero} at {table.sede}')
    return redirect('pedidos:order_detail', pk=order.pk)


@role_required('WAITER')
def order_detail(request, pk):
    order = get_object_or_404(Pedido.objects.select_related('mesa', 'mesa__sede'), pk=pk, mesa__sede=get_sede_efectiva(request))
    _assert_owner(request, order.mesero_id)
    details = list(order.detalles.select_related('producto').order_by('producto__nombre'))
    products, edit_detail, edit_products = [], None, []
    if order.estado == Pedido.Estado.OPEN:
        site = order.mesa.sede
        stock = dict(Inventario.objects.filter(sede=site).values_list('producto_id', 'cantidad'))
        reserved = reservas_por_producto(site)
        # Solo se ofrecen productos con unidades libres (existencia menos lo que ya está en pedidos abiertos).
        products = [p for p in Producto.objects.filter(activo=True, pk__in=stock).order_by('nombre')
                    if stock.get(p.pk, 0) - reserved.get(p.pk, 0) > 0]
        for p in products:
            p.free_units = stock[p.pk] - reserved.get(p.pk, 0)
        # HU024-E1: edición en el panel derecho (?edit=<línea>).
        edit_id = _integer(request.GET.get('edit'))
        edit_detail = next((d for d in details if d.pk == edit_id), None)
        if edit_detail:
            own = {d.producto_id for d in details}
            edit_products = [p for p in Producto.objects.filter(activo=True, pk__in=set(stock) | own).order_by('nombre')
                             if p.pk in own or stock.get(p.pk, 0) - reserved.get(p.pk, 0) > 0]
    total = sum(d.cantidad * d.valor_venta_unitario for d in details)
    return render(request, 'pedidos/order_detail.html', {'order': order, 'details': details, 'products': products,
                                                         'edit_detail': edit_detail, 'edit_products': edit_products,
                                                         'total': total})


@require_POST
@role_required('WAITER')
def add_product(request, pk):
    product_id, qty = _integer(request.POST.get('product')), _integer(request.POST.get('quantity'))
    if product_id is None or qty is None or not 1 <= qty <= 100000:
        messages.error(request, 'Choose a valid product and quantity.')
        return redirect('pedidos:order_detail', pk=pk)
    with transaction.atomic():
        order = get_object_or_404(Pedido.objects.select_for_update().select_related('mesa'), pk=pk, mesa__sede=get_sede_efectiva(request), estado=Pedido.Estado.OPEN)
        _assert_owner(request, order.mesero_id)
        product = get_object_or_404(Producto, pk=product_id, activo=True)
        # Lock the inventory row before counting reservations. This serializes
        # concurrent additions for the same product and site on MySQL/InnoDB.
        inventory = Inventario.objects.select_for_update().filter(
            producto=product, sede=order.mesa.sede
        ).first()
        detail = DetallePedido.objects.filter(pedido=order, producto=product).first()
        updated_qty = qty + (detail.cantidad if detail else 0)
        reserved = (DetallePedido.objects.filter(
            producto=product,
            pedido__estado=Pedido.Estado.OPEN,
            pedido__mesa__sede=order.mesa.sede,
        ).aggregate(total=Sum('cantidad'))['total'] or 0)
        # qty is the newly requested amount; existing details are already
        # included in reserved. No physical stock is deducted at this stage.
        if not inventory or reserved + qty > inventory.cantidad:
            messages.error(request, mensaje_sin_stock(product, inventory.cantidad if inventory else 0, reserved))
            return redirect('pedidos:order_detail', pk=pk)
        if detail:
            detail.cantidad = updated_qty
            detail.save(update_fields=['cantidad'])
        else:
            DetallePedido.objects.create(pedido=order, producto=product, cantidad=qty, valor_venta_unitario=product.valor_venta, valor_compra_unitario=product.valor_compra)
        registrar(request, 'ORDER_EDIT', 'Pedido', order, f'Added {qty} units of product #{product.pk}')
    return redirect('pedidos:order_detail', pk=pk)


@require_POST
@role_required('WAITER')
def remove_product(request, pk, detail_id):
    with transaction.atomic():
        order = get_object_or_404(Pedido.objects.select_for_update(), pk=pk, mesa__sede=get_sede_efectiva(request), estado=Pedido.Estado.OPEN)
        _assert_owner(request, order.mesero_id)
        detail = get_object_or_404(DetallePedido, pk=detail_id, pedido=order)
        if order.detalles.count() <= 1:
            # HU024-E3: el pedido conserva al menos un producto (coherente con HU025).
            messages.error(request, 'An order must have at least one product')
            return redirect('pedidos:order_detail', pk=pk)
        product_id = detail.producto_id
        detail.delete()
        registrar(request, 'ORDER_EDIT', 'Pedido', order, f'Removed product #{product_id}')
    return redirect('pedidos:order_detail', pk=pk)


def _reserved(product, site, exclude_detail=None):
    """Unidades del producto ya comprometidas en pedidos abiertos de la sede."""
    qs = DetallePedido.objects.filter(producto=product, pedido__estado=Pedido.Estado.OPEN, pedido__mesa__sede=site)
    if exclude_detail is not None:
        qs = qs.exclude(pk=exclude_detail.pk)
    return qs.aggregate(total=Sum('cantidad'))['total'] or 0


@require_POST
@role_required('WAITER')
def edit_item(request, pk, detail_id):
    """HU024-E1: corregir la cantidad o el producto de una línea mientras el pedido está abierto.

    Misma regla de stock que add_product: se bloquea la fila de inventario y se valida contra
    lo reservado por los demás pedidos abiertos de la sede. Si el producto nuevo ya está en el
    pedido, las dos líneas se unen (HU023-E3: una línea por producto).
    """
    product_id, qty = _integer(request.POST.get('product')), _integer(request.POST.get('quantity'))
    if product_id is None or qty is None or not 1 <= qty <= 100000:
        messages.error(request, 'Choose a valid product and quantity.')
        return redirect('pedidos:order_detail', pk=pk)
    with transaction.atomic():
        order = get_object_or_404(Pedido.objects.select_for_update().select_related('mesa'), pk=pk,
                                  mesa__sede=get_sede_efectiva(request), estado=Pedido.Estado.OPEN)
        _assert_owner(request, order.mesero_id)
        detail = get_object_or_404(DetallePedido.objects.select_for_update(), pk=detail_id, pedido=order)
        product = get_object_or_404(Producto, pk=product_id, activo=True)
        site = order.mesa.sede
        inventory = Inventario.objects.select_for_update().filter(producto=product, sede=site).first()
        other = None
        if product.pk != detail.producto_id:
            other = DetallePedido.objects.select_for_update().filter(pedido=order, producto=product).first()
        # Lo reservado por todos los demás (excluye la línea que se edita); si se une con otra
        # línea del mismo pedido, esa línea ya está incluida y se suma qty.
        reserved = _reserved(product, site, exclude_detail=detail)
        if not inventory or reserved + qty > inventory.cantidad:
            messages.error(request, mensaje_sin_stock(product, inventory.cantidad if inventory else 0, reserved))
            return redirect(f"{reverse('pedidos:order_detail', args=[pk])}?edit={detail.pk}")
        before = f'{detail.cantidad} x product #{detail.producto_id}'
        if other:
            other.cantidad += qty
            other.save(update_fields=['cantidad'])
            detail.delete()
        elif product.pk != detail.producto_id:
            detail.producto = product
            detail.cantidad = qty
            detail.valor_venta_unitario = product.valor_venta
            detail.valor_compra_unitario = product.valor_compra
            detail.save()
        else:
            detail.cantidad = qty
            detail.save(update_fields=['cantidad'])
        registrar(request, 'ORDER_EDIT', 'Pedido', order, f'Edited line: {before} -> {qty} x product #{product.pk}')
    messages.success(request, 'Order item updated.')
    return redirect('pedidos:order_detail', pk=pk)


@require_POST
@role_required('WAITER')
def save_order(request, pk):
    """HU025: guardar el pedido. Cada producto ya queda persistido al agregarlo; guardar confirma
    que el pedido está listo y visible para el cajero, y exige al menos un producto."""
    order = get_object_or_404(Pedido, pk=pk, mesa__sede=get_sede_efectiva(request), estado=Pedido.Estado.OPEN)
    _assert_owner(request, order.mesero_id)
    if not order.detalles.exists():
        messages.error(request, 'You must add at least one product')
        return redirect('pedidos:order_detail', pk=pk)
    registrar(request, 'ORDER_SAVE', 'Pedido', order, f'Saved order #{order.pk} for table {order.mesa.numero}')
    messages.success(request, f'Order #{order.pk} saved. The cashier can now collect payment.')
    return redirect('pedidos:tables')


@require_POST
@role_required('WAITER')
def cancel_order(request, pk):
    """Cancelar un pedido abierto que no se va a pagar (el cliente se fue o desistió).

    Los productos vuelven a quedar libres para las demás mesas (nunca se descontaron del
    inventario: eso solo ocurre al pagar). El pedido se elimina porque los únicos estados del
    negocio son OPEN y CLOSED; la bitácora conserva quién lo canceló y qué contenía. La mesa
    sigue ocupada hasta que el mesero la libera (Release table), igual que al descartar un
    pedido vacío.
    """
    with transaction.atomic():
        order = get_object_or_404(Pedido.objects.select_for_update().select_related('mesa'), pk=pk,
                                  mesa__sede=get_sede_efectiva(request), estado=Pedido.Estado.OPEN)
        _assert_owner(request, order.mesero_id)
        lines = list(order.detalles.select_related('producto').order_by('producto__nombre'))
        summary = ', '.join(f'{d.cantidad} x {d.producto.nombre}' for d in lines) or 'no products'
        registrar(request, 'ORDER_CANCEL', 'Pedido', order,
                  f'Cancelled unpaid order #{order.pk}, table {order.mesa.numero}: {summary}')
        number = order.mesa.numero
        order.delete()
    messages.success(request, f'Order cancelled; its products are available again. '
                              f'Release table {number} when the guests leave.')
    return redirect('pedidos:tables')


@require_POST
@role_required('WAITER')
def discard_empty(request, pk):
    with transaction.atomic():
        order = get_object_or_404(Pedido.objects.select_for_update(), pk=pk, mesa__sede=get_sede_efectiva(request), estado=Pedido.Estado.OPEN)
        _assert_owner(request, order.mesero_id)
        if order.detalles.exists():
            messages.error(request, 'Only empty orders may be discarded.')
            return redirect('pedidos:order_detail', pk=pk)
        registrar(request, 'ORDER_DISCARD', 'Pedido', order, 'Discarded an empty order')
        table = Mesa.objects.select_for_update().get(pk=order.mesa_id)
        order.delete()
        # Descartar una orden vacía NO termina la atención ni borra su responsable.
        # La mesa se libera exclusivamente mediante Release table.
    return redirect('pedidos:tables')


@require_POST
@role_required('WAITER')
def release_table(request, table_id):
    with transaction.atomic():
        table = _table(request, table_id, lock=True)
        _assert_table_owner(request, table)
        if Pedido.objects.filter(mesa=table, estado=Pedido.Estado.OPEN).exists():
            messages.error(request, 'A table with an open order cannot be released.')
            return redirect('pedidos:tables')
        if table.estado == Mesa.Estado.OCCUPIED:
            table.estado = Mesa.Estado.AVAILABLE
            table.responsable_actual = None
            table.save(update_fields=['estado', 'responsable_actual'])
            registrar(request, 'TABLE_RELEASE', 'Mesa', table, f'Released table {table.numero} at {table.sede}')
    return redirect('pedidos:tables')


@role_required('ADMIN')
def manage_tables(request):
    """Administrator: inspect all tables for one selected site, including inactive ones."""
    sites = Sede.objects.filter(activo=True).order_by('nombre')
    site_id = _integer(request.GET.get('site'))
    site = get_object_or_404(Sede, pk=site_id, activo=True) if site_id is not None else sites.first()
    items = quick_sort(Mesa.objects.filter(sede=site) if site else [], key=lambda t: (t.numero, t.pk))
    open_ids = set(Pedido.objects.filter(mesa__in=items, estado=Pedido.Estado.OPEN).values_list('mesa_id', flat=True))
    for table in items:
        table.has_open_order = table.pk in open_ids
    return render(request, 'pedidos/manage_tables.html', {'sites': sites, 'site': site, 'tables': items})


@require_POST
@role_required('ADMIN')
def create_table(request):
    site = get_object_or_404(Sede, pk=_integer(request.POST.get('site')), activo=True)
    number = _integer(request.POST.get('number'))
    if number is None or number < 1:
        messages.error(request, 'Enter a valid positive table number.')
    else:
        try:
            with transaction.atomic():
                table = Mesa.objects.create(sede=site, numero=number)
                registrar(request, 'TABLE_CREATE', 'Mesa', table, f'Created table {number} at {site}')
            messages.success(request, f'Table {number} created.')
        except IntegrityError:
            messages.error(request, 'This table number already exists at this site. Reactivate it instead.')
    return redirect(f'{reverse("pedidos:manage_tables")}?site={site.pk}')


@require_POST
@role_required('ADMIN')
def toggle_table(request, table_id):
    with transaction.atomic():
        table = get_object_or_404(Mesa.objects.select_for_update().select_related('sede'), pk=table_id)
        if not table.sede.activo:
            messages.error(request, 'This site is inactive.')
        elif table.activo and Pedido.objects.filter(mesa=table, estado=Pedido.Estado.OPEN).exists():
            messages.error(request, 'Cannot disable a table with an open order.')
        elif table.activo and table.estado == Mesa.Estado.OCCUPIED:
            messages.error(request, 'Release the occupied table before disabling it.')
        else:
            table.activo = not table.activo
            table.save(update_fields=['activo'])
            registrar(request, 'TABLE_ENABLE' if table.activo else 'TABLE_DISABLE', 'Mesa', table,
                      f'{"Enabled" if table.activo else "Disabled"} table {table.numero} at {table.sede}')
            messages.success(request, f'Table {table.numero} {"enabled" if table.activo else "disabled"}.')
    return redirect(f'{reverse("pedidos:manage_tables")}?site={table.sede_id}')
