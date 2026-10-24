"""Waiter operations. Payment and stock deduction belong to the cashier sprint."""
from django.contrib import messages
from django.db import IntegrityError, transaction
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


def _integer(value):
    return int(value) if value and value.isascii() and value.isdecimal() and len(value) <= 9 else None


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
    items = quick_sort(Mesa.objects.filter(sede=site, activo=True), key=lambda mesa: (mesa.numero, mesa.pk))
    open_orders = {order.mesa_id: order.pk for order in Pedido.objects.filter(mesa__in=items, estado=Pedido.Estado.OPEN)}
    for item in items:
        item.open_order_id = open_orders.get(item.pk)
        item.has_open_order = bool(item.open_order_id)
    return render(request, 'pedidos/tables.html', {'tables': items, 'site': site})


@require_POST
@role_required('WAITER')
def open_order(request, table_id):
    with transaction.atomic():
        table = _table(request, table_id, lock=True)
        if Pedido.objects.filter(mesa=table, estado=Pedido.Estado.OPEN).exists():
            messages.error(request, 'This table already has an open order.')
            return redirect('pedidos:tables')
        table.estado = Mesa.Estado.OCCUPIED
        table.save(update_fields=['estado'])
        order = Pedido.objects.create(mesa=table, mesero=request.user)
        registrar(request, 'ORDER_OPEN', 'Pedido', order, f'Opened order for table {table.numero} at {table.sede}')
    return redirect('pedidos:order_detail', pk=order.pk)


@role_required('WAITER')
def order_detail(request, pk):
    order = get_object_or_404(Pedido.objects.select_related('mesa', 'mesa__sede'), pk=pk, mesa__sede=get_sede_efectiva(request))
    details = list(order.detalles.select_related('producto').order_by('producto__nombre'))
    products = Producto.objects.filter(activo=True, inventario__sede=order.mesa.sede, inventario__cantidad__gt=0).distinct().order_by('nombre') if order.estado == Pedido.Estado.OPEN else []
    total = sum(d.cantidad * d.valor_venta_unitario for d in details)
    return render(request, 'pedidos/order_detail.html', {'order': order, 'details': details, 'products': products, 'total': total})


@require_POST
@role_required('WAITER')
def add_product(request, pk):
    product_id, qty = _integer(request.POST.get('product')), _integer(request.POST.get('quantity'))
    if product_id is None or qty is None or not 1 <= qty <= 100000:
        messages.error(request, 'Choose a valid product and quantity.')
        return redirect('pedidos:order_detail', pk=pk)
    with transaction.atomic():
        order = get_object_or_404(Pedido.objects.select_for_update().select_related('mesa'), pk=pk, mesa__sede=get_sede_efectiva(request), estado=Pedido.Estado.OPEN)
        product = get_object_or_404(Producto, pk=product_id, activo=True)
        inventory = Inventario.objects.filter(producto=product, sede=order.mesa.sede).first()
        detail = DetallePedido.objects.filter(pedido=order, producto=product).first()
        updated_qty = qty + (detail.cantidad if detail else 0)
        if not inventory or inventory.cantidad < updated_qty:
            messages.error(request, 'Insufficient stock for this product.')
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
        detail = get_object_or_404(DetallePedido, pk=detail_id, pedido=order)
        product_id = detail.producto_id
        detail.delete()
        registrar(request, 'ORDER_EDIT', 'Pedido', order, f'Removed product #{product_id}')
    return redirect('pedidos:order_detail', pk=pk)


@require_POST
@role_required('WAITER')
def discard_empty(request, pk):
    with transaction.atomic():
        order = get_object_or_404(Pedido.objects.select_for_update(), pk=pk, mesa__sede=get_sede_efectiva(request), estado=Pedido.Estado.OPEN)
        if order.detalles.exists():
            messages.error(request, 'Only empty orders may be discarded.')
            return redirect('pedidos:order_detail', pk=pk)
        registrar(request, 'ORDER_DISCARD', 'Pedido', order, 'Discarded an empty order')
        order.delete()
    return redirect('pedidos:tables')


@require_POST
@role_required('WAITER')
def release_table(request, table_id):
    with transaction.atomic():
        table = _table(request, table_id, lock=True)
        if Pedido.objects.filter(mesa=table, estado=Pedido.Estado.OPEN).exists():
            messages.error(request, 'A table with an open order cannot be released.')
            return redirect('pedidos:tables')
        if table.estado == Mesa.Estado.OCCUPIED:
            table.estado = Mesa.Estado.AVAILABLE
            table.save(update_fields=['estado'])
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
