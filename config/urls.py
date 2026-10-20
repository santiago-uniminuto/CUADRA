from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),   # panel técnico de Django (solo desarrollo)
    path("", include("apps.autenticacion.urls")),
    path("users/", include("apps.usuarios.urls")),
    path("catalog/", include("apps.catalogo.urls")),
    path("inventory/", include("apps.inventario.urls")),
    path("orders/", include("apps.pedidos.urls")),
    path("payments/", include("apps.pagos.urls")),
    path("reports/", include("apps.reportes.urls")),
    path("audit/", include("apps.auditoria.urls")),
]
