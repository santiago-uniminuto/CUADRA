from .models import Bitacora


def ip_de(request):
    """
    IP de quien hace la petición. Detrás de Nginx se usa X-Real-IP, que Nginx escribe con la IP
    real y el cliente no puede falsificar (Gunicorn solo escucha en 127.0.0.1); sin Nginx, REMOTE_ADDR.
    """
    if request is None:
        return ""
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")


def evento(usuario, accion, entidad, detalle="", entidad_id=None):
    """Escribe una línea en la bitácora sin necesitar un objeto (inicios de sesión, intentos fallidos...)."""
    Bitacora.objects.create(usuario=usuario, accion=accion, entidad=entidad,
                            entidad_id=entidad_id, detalle=detalle[:255])


def registrar(request, accion, entidad, objeto, detalle=""):
    """Escribe una línea en la bitácora (requisito no funcional de trazabilidad)."""
    evento(request.user, accion, entidad, detalle, objeto.pk)


def entero(valor):
    """Entero a partir de texto, o None. Solo dígitos ASCII (str.isdigit() acepta caracteres como '²' y luego int() falla)."""
    import re
    return int(valor) if valor is not None and re.fullmatch(r"[0-9]{1,9}", str(valor)) else None
