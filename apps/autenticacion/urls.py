from django.urls import path

from . import views

app_name = "autenticacion"

urlpatterns = [
    path("login/", views.CuadraLoginView.as_view(), name="login"),
    path("logout/", views.CuadraLogoutView.as_view(), name="logout"),
    path("home/", views.HomeView.as_view(), name="home"),
]