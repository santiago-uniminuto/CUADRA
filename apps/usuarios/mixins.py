from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from .decorators import has_role_access
from .models import Usuario


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Solo el rol Administrator entra a estas vistas, y solo mientras NO esté
    actuando como mesero/cajero (modo actuación). Usa la misma regla que
    @role_required (has_role_access), así los dos estilos de vista (de clase y
    de función) siempre dan el mismo resultado.
    """

    def test_func(self):
        return has_role_access(self.request, (Usuario.Rol.ADMIN,))

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("You do not have permission to access this page.")
