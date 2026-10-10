"""
Control de acceso por rol (OWASP: autorización a nivel de vista, no solo de UI),
más el "modo actuación" del administrador.

Uso:  @role_required("ADMIN")
      @role_required("WAITER", "CASHIER")

Modo actuación (requisito de la Propuesta Comercial: el administrador "accede a
todas las funcionalidades de mesero y cajero"):
  - Un admin "puro" accede a todo.
  - Para operar EN NOMBRE de una sede como mesero o cajero activa el modo
    actuación (vistas act_as / return_to_admin). Mientras está activo solo ve
    las pantallas de ESE rol y de ESA sede; las de Administrador quedan
    bloqueadas como protección, hasta que vuelve a su rol ("Return to Admin").
  - Todo vive en la sesión. El rol real del usuario en la base de datos NUNCA
    cambia por esto.
La "sede activa" usa las mismas claves de sesión que ya guarda el login
(sede_activa_id / sede_activa_nombre).

Tanto el decorador (vistas de función) como AdminRequiredMixin (vistas de clase,
ver mixins.py) pasan por has_role_access(), para que haya UNA sola regla.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def get_actuando_como(request):
    """None si el admin no está actuando, o 'WAITER' / 'CASHIER'."""
    if request.user.is_authenticated and request.user.rol == "ADMIN":
        return request.session.get("actuando_como")
    return None


def get_rol_efectivo(request):
    """Rol bajo el cual se evalúa el acceso en este momento."""
    return get_actuando_como(request) or request.user.rol


def get_sede_efectiva(request):
    """Sede bajo la cual opera la vista: la elegida al actuar, o la propia."""
    if get_actuando_como(request):
        from .models import Sede
        sede = Sede.objects.filter(pk=request.session.get("sede_activa_id")).first()
        if sede:
            return sede
    return request.user.sede


def has_role_access(request, roles):
    """Regla única de acceso por rol, usada por el decorador y por el mixin."""
    actuando = get_actuando_como(request)
    if request.user.rol == "ADMIN" and not actuando:
        return True  # admin "puro": acceso total
    return (actuando or request.user.rol) in roles


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if not has_role_access(request, roles):
                raise PermissionDenied("You do not have permission to access this page.")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
