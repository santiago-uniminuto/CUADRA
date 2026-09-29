from django.conf import settings
from django.db import models


class Pago(models.Model):
    """Un único método por transacción (sin pagos combinados). Datáfono propio, sin pasarela."""

    class Metodo(models.TextChoices):
        CASH = "CASH", "Cash"
        DEBIT = "DEBIT", "Debit card"
        CREDIT = "CREDIT", "Credit card"

    pedido = models.OneToOneField("pedidos.Pedido", on_delete=models.PROTECT, related_name="pago")
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pagos_registrados")
    metodo_pago = models.CharField(max_length=6, choices=Metodo.choices)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
