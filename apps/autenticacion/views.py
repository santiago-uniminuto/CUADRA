from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView
 
from .forms import CuadraAuthenticationForm
 
 
class CuadraLoginView(LoginView):
    """
    HU001 — Login.
 
    On top of authenticating, stores the "sede activa" (active site) in the
    session so that later sprints can read it without touching the login
    view again:
 
    - Administrator: defaults to the sede assigned to their user. It is a
      *default* because a future sprint will add a selector so the admin
      (who acts as superuser across the 3 sedes) can switch it.
    - Waiter / Cashier: always the sede assigned to their user. They get no
      selector, but we still store it for consistency, so any future view
      can read request.session["sede_activa_id"] without first checking
      the role.
    """
 
    template_name = "autenticacion/login.html"
    authentication_form = CuadraAuthenticationForm
    redirect_authenticated_user = True
 
    def form_valid(self, form):
        # super().form_valid() already calls auth_login(request, user)
        response = super().form_valid(form)
        usuario = form.get_user()
        self.request.session["sede_activa_id"] = usuario.sede_id
        self.request.session["sede_activa_nombre"] = usuario.sede.nombre
        return response
 
 
class CuadraLogoutView(LogoutView):
    """HU003 — Manual logout."""
 
    next_page = "autenticacion:login"
 
class HomeView(LoginRequiredMixin, TemplateView):
    """Temporary placeholder screen, just to verify login/logout and the
    active-sede session data while the real per-role dashboards get built
    in later sprints. Safe to delete once those exist."""
 
    template_name = "autenticacion/home.html"
 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sede_activa_id"] = self.request.session.get("sede_activa_id")
        context["sede_activa_nombre"] = self.request.session.get("sede_activa_nombre")
        return context
        
        