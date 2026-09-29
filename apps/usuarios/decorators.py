"""
Control de acceso por rol (OWASP: autorización a nivel de vista, no solo de UI).
Uso:  @role_required("ADMIN")
      @role_required("WAITER", "CASHIER")
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.rol not in roles:
                raise PermissionDenied("You do not have permission to access this page.")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
