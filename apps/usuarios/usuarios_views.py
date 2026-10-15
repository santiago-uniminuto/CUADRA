"""
Sprint 2 — Gestión de usuarios (HU004 a HU009 y HU033). Solo para el rol Administrator.

También contiene las dos vistas del modo actuación del admin (act_as / return_to_admin),
ver decorators.py.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from apps.algoritmos.ordenamiento import bubble_sort
from apps.auditoria.models import Bitacora

from .decorators import role_required
from .forms import AsignarRolSedeForm, ResetPasswordForm, UsuarioCreateForm, UsuarioUpdateForm
from .mixins import AdminRequiredMixin
from .models import Sede, Usuario


def _log(request, accion, usuario, detalle=""):
    """Registra la acción en la bitácora (requisito no funcional de trazabilidad)."""
    Bitacora.objects.create(
        usuario=request.user, accion=accion, entidad="Usuario",
        entidad_id=usuario.pk, detalle=detalle[:255],
    )


def cerrar_sesiones_de(usuario):
    """HU006 Escenario 4: elimina todas las sesiones abiertas del usuario."""
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if session.get_decoded().get("_auth_user_id") == str(usuario.pk):
            session.delete()


class UsuarioListView(AdminRequiredMixin, ListView):
    """HU009 — Listar usuarios (con búsqueda por nombre) + panel de reasignación HU007."""

    model = Usuario
    template_name = "usuarios/usuario_list.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        qs = Usuario.objects.select_related("sede")
        self.query = self.request.GET.get("q", "").strip()
        if self.query:
            qs = qs.filter(Q(nombre__icontains=self.query))
        # Orden por nombre con ordenamiento burbuja (requisito académico de
        # algoritmos), sin distinguir mayúsculas de minúsculas.
        return bubble_sort(qs, key=lambda u: (u.nombre.lower(), u.username.lower()))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["query"] = self.query
        ctx["roles"] = Usuario.Rol.choices
        ctx["sedes"] = Sede.objects.filter(activo=True).order_by("nombre")
        ctx["all_users"] = Usuario.objects.order_by("nombre")
        ctx["preselected"] = self.request.GET.get("assign", "")
        return ctx


class UsuarioCreateView(AdminRequiredMixin, CreateView):
    """HU004 — Crear usuario."""

    model = Usuario
    form_class = UsuarioCreateForm
    template_name = "usuarios/usuario_form.html"
    success_url = reverse_lazy("usuarios:usuario_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "New user"
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        _log(self.request, "CREATE", self.object, f"Created user {self.object.username} ({self.object.rol})")
        messages.success(self.request, "User created successfully.")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class UsuarioUpdateView(AdminRequiredMixin, UpdateView):
    """HU005 — Editar usuario."""

    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = "usuarios/usuario_form.html"
    success_url = reverse_lazy("usuarios:usuario_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["editing_self"] = self.object.pk == self.request.user.pk
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = f"Edit user — {self.object.username}"
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        _log(self.request, "UPDATE", self.object, f"Updated user {self.object.username}")
        messages.success(self.request, "User updated successfully.")
        return response


class UsuarioAssignView(AdminRequiredMixin, View):
    """HU007 — Reasignar rol y sede desde el listado (solo POST)."""

    http_method_names = ["post"]

    def post(self, request):
        form = AsignarRolSedeForm(request.POST, current_user=request.user)
        if form.is_valid():
            usuario = form.cleaned_data["usuario"]
            usuario.rol = form.cleaned_data["rol"]          # reemplaza el rol anterior: único rol activo
            usuario.sede = form.cleaned_data["sede"]
            usuario.save(update_fields=["rol", "sede"])
            _log(request, "UPDATE", usuario, f"Reassigned to {usuario.rol} / {usuario.sede}")
            messages.success(request, f"{usuario.username} is now {usuario.get_rol_display()} at {usuario.sede}.")
        elif any("own Administrator" in e for e in form.errors.get("rol", [])):
            messages.error(request, "You cannot remove your own Administrator role.")
        else:
            messages.error(request, "User, role and site are required.")
        return redirect("usuarios:usuario_list")


class UsuarioDeactivateView(AdminRequiredMixin, View):
    """HU006 — Desactivar usuario: GET pide confirmación, POST ejecuta."""

    def get(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        return render(request, "usuarios/usuario_confirm_deactivate.html", {"usuario": usuario})

    def post(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        if usuario.pk == request.user.pk:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("usuarios:usuario_list")
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])
        cerrar_sesiones_de(usuario)
        _log(request, "DEACTIVATE", usuario, f"Deactivated user {usuario.username}")
        messages.success(request, f"User {usuario.username} was deactivated.")
        return redirect("usuarios:usuario_list")


class UsuarioReactivateView(AdminRequiredMixin, View):
    """HU033 — Reactivar usuario: GET pide confirmación, POST ejecuta."""

    def _sede_inactiva(self, request, usuario):
        if not usuario.sede.activo:
            messages.error(request, f"Site {usuario.sede} is inactive. Reactivate the site or reassign the user first.")
            return True
        return False

    def get(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        if self._sede_inactiva(request, usuario):
            return redirect("usuarios:usuario_list")
        return render(request, "usuarios/usuario_confirm_reactivate.html", {"usuario": usuario})

    def post(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        if self._sede_inactiva(request, usuario):
            return redirect("usuarios:usuario_list")
        if usuario.is_active:
            messages.info(request, f"User {usuario.username} is already active.")
            return redirect("usuarios:usuario_list")
        usuario.is_active = True
        usuario.save(update_fields=["is_active"])
        _log(request, "REACTIVATE", usuario, f"Reactivated user {usuario.username}")
        messages.success(request, f"User {usuario.username} was reactivated.")
        return redirect("usuarios:usuario_list")


class UsuarioResetPasswordView(AdminRequiredMixin, View):
    """HU008 — Restablecer contraseña."""

    template_name = "usuarios/usuario_reset_password.html"

    def get(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        return render(request, self.template_name, {"usuario": usuario, "form": ResetPasswordForm(usuario=usuario)})

    def post(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk)
        form = ResetPasswordForm(request.POST, usuario=usuario)
        if form.is_valid():
            form.save()
            _log(request, "UPDATE", usuario, f"Password reset for {usuario.username}")
            messages.success(request, f"Password for {usuario.username} was reset.")
            return redirect("usuarios:usuario_list")
        return render(request, self.template_name, {"usuario": usuario, "form": form})


# ---------------------------------------------------------------- Modo actuación del admin
def _log_actuacion(request, accion, sede, detalle):
    Bitacora.objects.create(
        usuario=request.user, accion=accion, entidad="Sede",
        entidad_id=sede.pk if sede else None, detalle=detalle[:255],
    )


@role_required("ADMIN")
@require_POST
def act_as(request):
    """
    El admin empieza a actuar como mesero o cajero de UNA sede. Solo se guarda
    en la sesión: el rol real en la base de datos no cambia. Reutiliza la
    "sede activa" que ya guarda el login.
    """
    rol = request.POST.get("rol")
    sede = Sede.objects.filter(pk=request.POST.get("sede") or None, activo=True).first()
    if rol not in (Usuario.Rol.MESERO, Usuario.Rol.CAJERO) or sede is None:
        messages.error(request, "Choose a role (Waiter or Cashier) and a site.")
        return redirect("autenticacion:home")
    request.session["actuando_como"] = rol
    request.session["sede_activa_id"] = sede.pk
    request.session["sede_activa_nombre"] = sede.nombre
    _log_actuacion(request, "ACT_AS", sede, f"Admin acting as {rol} at {sede.nombre}")
    return redirect("autenticacion:home")


@login_required
@require_POST
def return_to_admin(request):
    """Sale del modo actuación: vuelve a las pantallas de Administrador y a su sede propia."""
    if request.session.pop("actuando_como", None):
        _log_actuacion(request, "RETURN_TO_ADMIN", request.user.sede, "Admin left acting mode")
    request.session["sede_activa_id"] = request.user.sede_id
    request.session["sede_activa_nombre"] = request.user.sede.nombre
    return redirect("reportes:dashboard")
