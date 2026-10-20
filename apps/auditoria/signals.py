"""
Eventos de seguridad en la bitácora, sin tocar las vistas de login:
iniciar sesión, cerrar sesión e intentos fallidos. Se conectan en AuditoriaConfig.ready().
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .utils import evento, ip_de


@receiver(user_logged_in)
def al_iniciar_sesion(sender, request, user, **kwargs):
    evento(user, "LOGIN", "Usuario", f"from {ip_de(request)}", user.pk)


@receiver(user_logged_out)
def al_cerrar_sesion(sender, request, user, **kwargs):
    if user is None or getattr(request, "_cierre_por_inactividad", False):
        return  # el cierre por inactividad se registra aparte (SESSION_EXPIRED)
    evento(user, "LOGOUT", "Usuario", f"from {ip_de(request)}", user.pk)


@receiver(user_login_failed)
def al_fallar_el_login(sender, credentials, request=None, **kwargs):
    """
    Se guarda el usuario SOLO si existe. Si el nombre no existe no se guarda lo que escribieron:
    mucha gente teclea su contraseña en el campo de usuario y no debe quedar en la bitácora.
    """
    from apps.usuarios.models import Usuario

    nombre = (credentials or {}).get("username") or ""
    usuario = Usuario.objects.filter(username__iexact=nombre).first() if nombre else None
    evento(usuario, "LOGIN_FAILED", "Usuario", f"from {ip_de(request)}", usuario.pk if usuario else None)
