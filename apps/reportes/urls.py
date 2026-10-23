from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    # Los reportes de ventas e inventario (Sprint 5) se agregan aquí.
]

from .operational import inventory_report, sales_report
urlpatterns += [
    path('sales/', sales_report, name='sales'),
    path('inventory/', inventory_report, name='inventory'),
]

from .operational import inventory_export, sales_export
urlpatterns += [
    path('sales/export/', sales_export, name='sales_export'),
    path('inventory/export/', inventory_export, name='inventory_export'),
]

from .operational import general_report, general_export
urlpatterns += [
    path('general/', general_report, name='general'),
    path('general/export/', general_export, name='general_export'),
]

from .top_products import top_products_report
urlpatterns += [path('top-products/', top_products_report, name='top_products')]
