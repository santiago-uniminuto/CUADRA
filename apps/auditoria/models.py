from django.conf import settings
from django.db import models


# Nombre legible de cada acción y su categoría (solo para mostrar; el esquema no cambia).
ACCIONES = {
    "LOGIN": ("Signed in", "access"),
    "LOGOUT": ("Signed out", "access"),
    "LOGIN_FAILED": ("Failed sign-in", "security"),
    "SESSION_EXPIRED": ("Session expired (inactivity)", "security"),
    "SESSION_REPLACED": ("Session closed (signed in elsewhere)", "security"),
    "CREATE": ("Created", "change"),
    "UPDATE": ("Updated", "change"),
    "DEACTIVATE": ("Deactivated", "change"),
    "REACTIVATE": ("Reactivated", "change"),
    "STOCK_IN": ("Stock received", "change"),
    "STOCK_ADJUST": ("Stock adjusted", "change"),
    "ACT_AS": ("Acting mode started", "change"),
    "RETURN_TO_ADMIN": ("Acting mode ended", "change"),
    "ORDER_OPEN": ("Order opened", "change"),
    "ORDER_EDIT": ("Order updated", "change"),
    "ORDER_SAVE": ("Order saved", "change"),
    "ORDER_DISCARD": ("Empty order discarded", "change"),
    "ORDER_CANCEL": ("Unpaid order cancelled", "change"),
    "ORDER_CLOSE": ("Order closed", "change"),
    "PAYMENT": ("Payment registered", "change"),
    "TABLE_RELEASE": ("Table released", "change"),
    "TABLE_CREATE": ("Table created", "change"),
    "TABLE_ENABLE": ("Table enabled", "change"),
    "TABLE_DISABLE": ("Table disabled", "change"),
}


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

    @property
    def quien(self):
        """Quién hizo la acción, listo para mostrar. Sin usuario (intento fallido con un nombre que no existe) es «Unknown user»."""
        if self.usuario_id is None:
            return "Unknown user"
        return self.usuario.nombre or self.usuario.username

    @property
    def accion_legible(self):
        return ACCIONES.get(self.accion, (self.accion, "change"))[0]

    @property
    def categoria(self):
        return ACCIONES.get(self.accion, (self.accion, "change"))[1]
