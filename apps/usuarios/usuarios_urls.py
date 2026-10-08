from django.urls import path

from . import usuarios_views as views

urlpatterns = [
    path("", views.UsuarioListView.as_view(), name="usuario_list"),
    path("new/", views.UsuarioCreateView.as_view(), name="usuario_create"),
    path("assign/", views.UsuarioAssignView.as_view(), name="usuario_assign"),
    path("<int:pk>/edit/", views.UsuarioUpdateView.as_view(), name="usuario_update"),
    path("<int:pk>/deactivate/", views.UsuarioDeactivateView.as_view(), name="usuario_deactivate"),
    path("<int:pk>/reset-password/", views.UsuarioResetPasswordView.as_view(), name="usuario_reset_password"),
]
