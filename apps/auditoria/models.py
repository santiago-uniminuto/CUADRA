from django.conf import settings
from django.db import models


class Bitacora(models.Model):
    """
    Trazabilidad de las acciones de los usuarios (requisito no funcional).
    Solo se inserta; nunca se edita ni se borra desde la aplicación.
    'usuario' puede ser nulo para registrar, por ejemplo, intentos de login fallidos.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="bitacora")
    accion = models.CharField(max_length=40)     # LOGIN, LOGOUT, CREATE, UPDATE, DEACTIVATE, CLOSE_ORDER, PAY...
    entidad = models.CharField(max_length=40)    # Usuario, Producto, Pedido, Pago...
    entidad_id = models.PositiveIntegerField(null=True, blank=True)
    detalle = models.CharField(max_length=255, blank=True)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["usuario", "fecha"])]
