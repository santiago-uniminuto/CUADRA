"""Cashier checkout. Payment, inventory and order closure are one transaction."""
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from apps.algoritmos.calculos import desglose_vuelto, sumatoria
from apps.auditoria.utils import registrar
from apps.inventario.models import Inventario
from apps.pedidos.models import Pedido
from apps.usuarios.decorators import get_actuando_como, get_sede_efectiva, role_required
from .models import Pago


@role_required('CASHIER')
def checkout_queue(request):
    # HU025-E1: el cajero ve los pedidos abiertos que ya tienen productos guardados.
    orders = (Pedido.objects.filter(mesa__sede=get_sede_efectiva(request), estado=Pedido.Estado.OPEN,
                                    detalles__isnull=False).distinct()
              .select_related('mesa', 'mesero').prefetch_related('detalles').order_by('fecha'))
    for order in orders:
        order.total = sumatoria((d.cantidad * d.valor_venta_unitario for d in order.detalles.all()), Decimal('0.00'))
    return render(request, 'pagos/queue.html', {'orders': orders})


@role_required('CASHIER')
def checkout_detail(request, pk):
    order = get_object_or_404(Pedido.objects.select_related('mesa', 'mesero'), pk=pk,
                              mesa__sede=get_sede_efectiva(request))
    details = list(order.detalles.select_related('producto').order_by('producto__nombre'))
    total = sumatoria((d.cantidad * d.valor_venta_unitario for d in details), Decimal('0.00'))
    payment = Pago.objects.filter(pedido=order).first()
    change_breakdown, change_remainder = [], Decimal('0.00')
    if payment and payment.cambio:
        # Algoritmo voraz: billetes y monedas a devolver, de mayor a menor.
        pairs, change_remainder = desglose_vuelto(payment.cambio)
        change_breakdown = [{'value': value, 'quantity': quantity} for value, quantity in pairs]
    return render(request, 'pagos/checkout.html', {'order': order, 'details': details,
                                                    'total': total, 'payment': payment,
                                                    'change_breakdown': change_breakdown,
                                                    'change_remainder': change_remainder,
                                                    'methods': Pago.Metodo.choices})


@require_POST
@role_required('CASHIER')
def register_payment(request, pk):
    method = request.POST.get('method', '')
    if method not in Pago.Metodo.values:
        messages.error(request, 'You must select a payment method')  # HU027-E2
        return redirect('pagos:checkout_detail', pk=pk)
    cash_received = None
    if method == Pago.Metodo.CASH:
        raw = request.POST.get('cash_received', '').strip()
        try:
            cash_received = Decimal(raw)
            if not cash_received.is_finite() or cash_received.as_tuple().exponent < -2 or cash_received < 0 or cash_received > Decimal('9999999999.99'):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            messages.error(request, 'Enter a valid cash amount (up to two decimal places).')
            return redirect('pagos:checkout_detail', pk=pk)
    with transaction.atomic():
        order = get_object_or_404(Pedido.objects.select_for_update().select_related('mesa'),
                                  pk=pk, mesa__sede=get_sede_efectiva(request))
        if order.estado != Pedido.Estado.OPEN or Pago.objects.filter(pedido=order).exists():
            messages.error(request, 'This order has already been paid or closed.')
            return redirect('pagos:checkout_detail', pk=pk)
        details = list(order.detalles.select_related('producto').order_by('producto_id'))
        if not details:
            messages.error(request, 'An empty order cannot be paid.')
            return redirect('pagos:checkout_detail', pk=pk)
        # Lock stock rows in a stable order; another checkout or stock adjustment
        # cannot deduct the same units simultaneously on MySQL/InnoDB.
        inventories = {i.producto_id: i for i in Inventario.objects.select_for_update().filter(
            sede=order.mesa.sede, producto_id__in=[d.producto_id for d in details]).order_by('producto_id')}
        for detail in details:
            inventory = inventories.get(detail.producto_id)
            if not inventory or inventory.cantidad < detail.cantidad:
                messages.error(request, f'Insufficient stock for {detail.producto.nombre}. No payment was registered.')
                return redirect('pagos:checkout_detail', pk=pk)
        total = sumatoria((d.cantidad * d.valor_venta_unitario for d in details), Decimal('0.00'))
        if method == Pago.Metodo.CASH and cash_received < total:
            messages.error(request, 'Cash received cannot be less than the order total.')
            return redirect('pagos:checkout_detail', pk=pk)
        for detail in details:
            inventory = inventories[detail.producto_id]
            inventory.cantidad -= detail.cantidad
            inventory.save(update_fields=['cantidad'])
        payment = Pago.objects.create(pedido=order, cajero=request.user, metodo_pago=method, valor=total,
                                    efectivo_recibido=cash_received,
                                    cambio=(cash_received - total if cash_received is not None else None))
        order.estado = Pedido.Estado.CLOSED
        order.save(update_fields=['estado'])
        registrar(request, 'ORDER_CLOSE', 'Pedido', order, f'Closed order #{order.pk}; total {total}')
        registrar(request, 'PAYMENT', 'Pago', payment, f'Payment for order #{order.pk}; method {method}; total {total}')
    messages.success(request, 'Payment registered. The table remains occupied until the waiter releases it.')
    return redirect('pagos:checkout_detail', pk=pk)


@role_required('CASHIER')
def payment_receipt(request, pk):
    """Read-only paid receipt: admin all sites; cashier own effective site."""
    payments = Pago.objects.select_related('pedido__mesa__sede', 'pedido__mesero', 'cajero')
    # Pure ADMIN can inspect receipts across all sites from Sales Report.
    # CASHIER (including an admin acting as cashier) stays scoped to one site.
    if request.user.rol != 'ADMIN' or get_actuando_como(request):
        payments = payments.filter(pedido__mesa__sede=get_sede_efectiva(request))
    payment = get_object_or_404(
        payments, pedido_id=pk, pedido__estado=Pedido.Estado.CLOSED,
    )
    details = list(payment.pedido.detalles.select_related('producto').order_by('pk'))
    lines = [
        {'name': detail.producto.nombre, 'quantity': detail.cantidad,
         'unit_price': detail.valor_venta_unitario,
         'subtotal': detail.cantidad * detail.valor_venta_unitario}
        for detail in details
    ]
    return render(request, 'pagos/receipt.html', {
        'payment': payment, 'order': payment.pedido, 'lines': lines,
        'receipt_admin_mode': request.user.rol == 'ADMIN' and not get_actuando_como(request),
    })
