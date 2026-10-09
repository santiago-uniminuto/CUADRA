from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, ListView, UpdateView

from .decorators import role_required
from .models import Sede


@method_decorator(role_required("ADMIN"), name="dispatch")
class SedeListView(ListView):
    """HU012 — Listar sedes."""

    model = Sede
    template_name = "usuarios/sede_list.html"
    context_object_name = "sedes"
    ordering = ["nombre"]


@method_decorator(role_required("ADMIN"), name="dispatch")
class SedeCreateView(CreateView):
    """HU010 — Crear sede."""

    model = Sede
    fields = ["nombre", "direccion"]
    template_name = "usuarios/sede_form.html"
    success_url = reverse_lazy("usuarios:sede_list")


@method_decorator(role_required("ADMIN"), name="dispatch")
class SedeUpdateView(UpdateView):
    """HU011 — Editar sede."""

    model = Sede
    fields = ["nombre", "direccion"]
    template_name = "usuarios/sede_form.html"
    success_url = reverse_lazy("usuarios:sede_list")
