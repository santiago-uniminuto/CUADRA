"""Unidades comprometidas en pedidos abiertos (reservadas, aún sin pagar).

El inventario físico solo se descuenta al registrar el pago. Mientras tanto, las unidades
que están en pedidos abiertos de la sede no se pueden ofrecer a otra mesa. Este módulo
calcula lo "disponible" que ven los meseros: existencia física menos lo reservado.
"""
from django.db.models import Sum

from .models import DetallePedido, Pedido


def reservas_por_producto(sede, exclude_detail=None):
    """{producto_id: unidades en pedidos abiertos de la sede}."""
    qs = DetallePedido.objects.filter(pedido__estado=Pedido.Estado.OPEN, pedido__mesa__sede=sede)
    if exclude_detail is not None:
        qs = qs.exclude(pk=exclude_detail.pk)
    return dict(qs.values("producto_id").annotate(total=Sum("cantidad")).values_list("producto_id", "total"))


def mensaje_sin_stock(producto, existencia, reservado):
    """Mensaje claro cuando no alcanzan las unidades libres (HU021 / HU020-E2)."""
    if existencia <= 0:
        return f"{producto.nombre} is out of stock."
    libres = max(existencia - reservado, 0)
    if libres == 0:
        return (f"All {existencia} unit(s) of {producto.nombre} are already in other open orders. "
                "They become available again if those orders are cancelled.")
    return (f"Only {libres} unit(s) of {producto.nombre} are free; the rest are in other open orders. "
            "They become available again if those orders are cancelled.")
