"""Ranking of products sold in successfully paid orders (Heap Sort)."""
from collections import defaultdict
from decimal import Decimal

from django.shortcuts import render

from apps.algoritmos.ordenamiento import heap_sort
from apps.pagos.models import Pago
from apps.pedidos.models import DetallePedido
from apps.usuarios.decorators import role_required
from apps.usuarios.models import Sede
from .operational import _apply_payment_date_filters, _filters, _site


@role_required('ADMIN', 'CASHIER')
def top_products_report(request):
    """Rank by paid units, with revenue computed from historical unit prices.

    The query is constrained to paid orders (not simply CLOSED orders),
    avoiding stock-only or unpaid activity. A single payment per order is
    enforced by the payment model and checkout workflow.
    """
    site, is_admin = _site(request)
    start, end, error = _filters(request)
    payments = Pago.objects.all()
    if site:
        payments = payments.filter(pedido__mesa__sede=site)
    payments = _apply_payment_date_filters(payments, start, end)

    ranking = []
    if not error:
        paid_ids = payments.values('pedido_id')
        # Revenue is calculated from frozen sale prices per order line,
        # not from today's catalog price.
        rows = (DetallePedido.objects.filter(pedido_id__in=paid_ids)
                .select_related('producto')
                .only('producto_id', 'producto__nombre', 'cantidad', 'valor_venta_unitario'))
        totals = defaultdict(lambda: {'units': 0, 'revenue': Decimal('0.00'), 'name': ''})
        for row in rows:
            item = totals[row.producto_id]
            item['name'] = row.producto.nombre
            item['units'] += row.cantidad
            item['revenue'] += row.valor_venta_unitario * row.cantidad
        ranking = [dict(product_id=pk, **values) for pk, values in totals.items()]
        ranking = heap_sort(ranking, key=lambda r: (-r['units'], r['name'].casefold(), r['product_id']))

    return render(request, 'reportes/top_products.html', {
        'ranking': ranking, 'error': error, 'site': site,
        'is_admin_report': is_admin,
        'sites': Sede.objects.order_by('nombre') if is_admin else [],
        'start': request.GET.get('start', ''), 'end': request.GET.get('end', ''),
    })
