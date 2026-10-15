from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    # Los reportes de ventas e inventario (Sprint 5) se agregan aquí.
]
