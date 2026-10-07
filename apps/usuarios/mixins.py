from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from .models import Usuario


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Solo usuarios con rol Administrator pueden entrar a estas vistas."""

    def test_func(self):
        return self.request.user.rol == Usuario.Rol.ADMIN

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Only administrators can manage sites.")
