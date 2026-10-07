from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from .mixins import AdminRequiredMixin
from .models import Sede


class SedeListView(AdminRequiredMixin, ListView):
    """HU012 — Listar sedes."""

    model = Sede
    template_name = "usuarios/sede_list.html"
    context_object_name = "sedes"
    ordering = ["nombre"]


class SedeCreateView(AdminRequiredMixin, CreateView):
    """HU010 — Crear sede."""

    model = Sede
    fields = ["nombre", "direccion"]
    template_name = "usuarios/sede_form.html"
    success_url = reverse_lazy("usuarios:sede_list")


class SedeUpdateView(AdminRequiredMixin, UpdateView):
    """HU011 — Editar sede."""

    model = Sede
    fields = ["nombre", "direccion"]
    template_name = "usuarios/sede_form.html"
    success_url = reverse_lazy("usuarios:sede_list")
