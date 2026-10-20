from django.urls import path

from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.inventario_list, name="inventario_list"),
    path("admin/", views.stock_list, name="stock_list"),
    path("admin/receive/", views.stock_receive, name="stock_receive"),
    path("admin/adjust/", views.stock_adjust, name="stock_adjust"),
]
