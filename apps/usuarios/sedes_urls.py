from django.urls import path

from . import sedes_views as views

app_name = "usuarios"

urlpatterns = [
    path("sedes/", views.SedeListView.as_view(), name="sede_list"),
    path("sedes/nueva/", views.SedeCreateView.as_view(), name="sede_create"),
    path("sedes/<int:pk>/editar/", views.SedeUpdateView.as_view(), name="sede_update"),
]
