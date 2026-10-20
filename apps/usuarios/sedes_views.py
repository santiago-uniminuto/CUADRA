from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.auditoria.utils import registrar

from .decorators import role_required
from .models import Sede


@method_decorator(role_required("ADMIN"), name="dispatch")
class SedeListView(ListView):
    """HU012 — Listar sedes."""

    model = Sede
    template_name = "usuarios/sede_list.html"
    context_object_name = "sedes"
    ordering = ["-activo", "nombre"]


@method_decorator(role_required("ADMIN"), name="dispatch")
class SedeCreateView(CreateView):
    """HU010 — Crear sede."""

    model = Sede
    fields = ["nombre", "direccion"]
    template_name = "usuarios/sede_form.html"
    success_url = reverse_lazy("usuarios:sede_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        registrar(self.request, "CREATE", "Sede", self.object, f"Created site {self.object.nombre}")
        return response


@method_decorator(role_required("ADMIN"), name="dispatch")
class SedeUpdateView(UpdateView):
    """HU011 — Editar sede."""

    model = Sede
    fields = ["nombre", "direccion"]
    template_name = "usuarios/sede_form.html"
    success_url = reverse_lazy("usuarios:sede_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        registrar(self.request, "UPDATE", "Sede", self.object, f"Updated site {self.object.nombre}")
        return response


@method_decorator(role_required("ADMIN"), name="dispatch")
class SedeToggleView(View):
    """
    Deshabilitar / reactivar una sede (nada se borra: se conserva el historial).
    Regla de protección: no se puede deshabilitar una sede mientras tenga usuarios
    activos; primero hay que reasignarlos o desactivarlos.
    """

    def _bloqueada(self, request, sede):
        if sede.activo and sede.usuarios.filter(is_active=True).exists():
            messages.error(request, f"Site {sede} still has active users. Reassign or deactivate them first.")
            return True
        return False

    def get(self, request, pk):
        sede = get_object_or_404(Sede, pk=pk)
        if self._bloqueada(request, sede):
            return redirect("usuarios:sede_list")
        return render(request, "confirm_toggle.html", {
            "objeto": sede, "nombre_en": "site", "reactivar": not sede.activo,
            "aviso": "" if not sede.activo else "It will no longer be offered when assigning users or acting as Waiter/Cashier. Its history is kept.",
            "cancel_url": "usuarios:sede_list",
        })

    def post(self, request, pk):
        sede = get_object_or_404(Sede, pk=pk)
        if self._bloqueada(request, sede):
            return redirect("usuarios:sede_list")
        reactivar = not sede.activo
        sede.activo = reactivar
        sede.save(update_fields=["activo"])
        registrar(request, "REACTIVATE" if reactivar else "DEACTIVATE", "Sede", sede,
                  f"{'Reactivated' if reactivar else 'Deactivated'} site {sede}")
        messages.success(request, f"Site {sede} was {'reactivated' if reactivar else 'deactivated'}.")
        return redirect("usuarios:sede_list")
