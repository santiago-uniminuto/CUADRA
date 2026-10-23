import time

from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.sessions.models import Session
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.auditoria.utils import evento, ip_de
from apps.usuarios.decorators import get_rol_efectivo
from apps.usuarios.models import Usuario

from .forms import CuadraAuthenticationForm


def close_other_sessions(user, current_session_key):
    """HU001, scenario 8 (single session): delete every other active session
    that belongs to this user, so the previous device is logged out."""
    closed = 0
    active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
    for session in active_sessions.exclude(session_key=current_session_key):
        if session.get_decoded().get("_auth_user_id") == str(user.pk):
            session.delete()
            closed += 1
    return closed


class CuadraLoginView(LoginView):
    """
    HU001 — Login.

    On top of authenticating, stores the "sede activa" (active site) in the
    session so that later sprints can read it without touching the login
    view again:

    - Administrator: defaults to the sede assigned to their user (a future
      selector will let the admin switch it).
    - Waiter / Cashier: always the sede assigned to their user.

    It also enforces a single session per user: logging in closes any other
    session the same user had open.
    """

    template_name = "autenticacion/login.html"
    authentication_form = CuadraAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        # super().form_valid() already calls auth_login(request, user)
        response = super().form_valid(form)
        usuario = form.get_user()
        session = self.request.session
        session["sede_activa_id"] = usuario.sede_id
        session["sede_activa_nombre"] = usuario.sede.nombre
        session["last_activity"] = time.time()
        if close_other_sessions(usuario, session.session_key):
            evento(usuario, "SESSION_REPLACED", "Usuario",
                   f"Previous session closed: signed in again from {ip_de(self.request)}", usuario.pk)
        return response


class CuadraLogoutView(View):
    """HU003 — Manual logout with confirmation.

    GET  -> shows "Are you sure you want to log out?" (YES / NO).
    POST -> (YES) closes the session and redirects to the login screen.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("autenticacion:login")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, "autenticacion/logout_confirm.html")

    def post(self, request):
        logout(request)
        return redirect("autenticacion:login")


class HomeView(LoginRequiredMixin, TemplateView):
    """
    HU001, escenario 1 — pantalla principal según el rol:

    - Administrator -> dashboard de inicio (bienvenida y resumen).
    - Waiter        -> inventario de su sede.
    - Cashier       -> cola de pagos pendientes.

    Si el admin está en modo actuación, se usa el rol con el que actúa.
    """

    template_name = "autenticacion/home.html"
    DESTINOS = {
        Usuario.Rol.ADMIN: "reportes:dashboard",
        Usuario.Rol.MESERO: "inventario:inventario_list",
        Usuario.Rol.CAJERO: "pagos:queue",
    }

    def get(self, request, *args, **kwargs):
        destino = self.DESTINOS.get(get_rol_efectivo(request))
        if destino:
            return redirect(destino)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sede_activa_id"] = self.request.session.get("sede_activa_id")
        context["sede_activa_nombre"] = self.request.session.get("sede_activa_nombre")
        return context
