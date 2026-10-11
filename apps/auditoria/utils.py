from .models import Bitacora


def registrar(request, accion, entidad, objeto, detalle=""):
    """Escribe una línea en la bitácora (requisito no funcional de trazabilidad)."""
    Bitacora.objects.create(
        usuario=request.user, accion=accion, entidad=entidad,
        entidad_id=objeto.pk, detalle=detalle[:255],
    )
