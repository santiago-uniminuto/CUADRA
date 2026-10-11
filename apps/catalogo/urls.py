from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("products/", views.producto_list, name="producto_list"),
    path("products/new/", views.producto_create, name="producto_create"),
    path("products/<int:pk>/edit/", views.producto_edit, name="producto_edit"),
    path("products/<int:pk>/toggle/", views.producto_toggle, name="producto_toggle"),

    path("suppliers/", views.proveedor_list, name="proveedor_list"),
    path("suppliers/new/", views.proveedor_create, name="proveedor_create"),
    path("suppliers/<int:pk>/edit/", views.proveedor_edit, name="proveedor_edit"),
    path("suppliers/<int:pk>/toggle/", views.proveedor_toggle, name="proveedor_toggle"),

    path("product-types/", views.tipoproducto_list, name="tipoproducto_list"),
    path("product-types/new/", views.tipoproducto_create, name="tipoproducto_create"),
    path("product-types/<int:pk>/toggle/", views.tipoproducto_toggle, name="tipoproducto_toggle"),
]
