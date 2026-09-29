from django.db import models


class Inventario(models.Model):
    """
    Cantidad disponible de cada producto en cada sede (resuelve N:M Producto-Sede).
    La 'PK compuesta' (producto, sede) se garantiza con UniqueConstraint.
    Unidades enteras: no hay inventario fraccionado.
    """
    producto = models.ForeignKey("catalogo.Producto", on_delete=models.PROTECT)
    sede = models.ForeignKey("usuarios.Sede", on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["producto", "sede"], name="uq_inventario_producto_sede"),
        ]
