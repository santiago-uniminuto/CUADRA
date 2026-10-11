from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Mesa(models.Model):
    class Estado(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        OCCUPIED = "OCCUPIED", "Occupied"

    numero = models.PositiveIntegerField()
    sede = models.ForeignKey("usuarios.Sede", on_delete=models.PROTECT, related_name="mesas")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.AVAILABLE)
    # Una mesa deshabilitada no se ofrece para nuevos pedidos pero conserva su historial.
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sede", "numero"], name="uq_mesa_sede_numero"),
        ]


class Pedido(models.Model):
    class Estado(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    mesa = models.ForeignKey(Mesa, on_delete=models.PROTECT, related_name="pedidos")
    mesero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pedidos_tomados")
    estado = models.CharField(max_length=6, choices=Estado.choices, default=Estado.OPEN)
    fecha = models.DateTimeField(auto_now_add=True)

    # OJO: "una mesa no puede tener 2 pedidos abiertos" NO se puede forzar con un índice
    # en MySQL (no soporta índices únicos parciales). Se valida en la lógica de negocio,
    # dentro de una transacción con select_for_update().


class DetallePedido(models.Model):
    """
    Productos de un pedido (resuelve N:M Pedido-Producto).
    Guarda el precio CONGELADO al momento de la venta: si luego cambia el precio del
    producto, los reportes históricos no se alteran.
    """
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey("catalogo.Producto", on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    valor_venta_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    valor_compra_unitario = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["pedido", "producto"], name="uq_detalle_pedido_producto"),
            models.CheckConstraint(condition=Q(cantidad__gte=1), name="ck_detalle_cantidad_positiva"),
        ]
