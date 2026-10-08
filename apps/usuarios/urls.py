from .sedes_urls import urlpatterns as sedes_urlpatterns
from .usuarios_urls import urlpatterns as usuarios_urlpatterns

app_name = "usuarios"

# Sprint 1: sedes (/users/sedes/...)   ·   Sprint 2: usuarios (/users/, /users/new/, ...)
urlpatterns = sedes_urlpatterns + usuarios_urlpatterns
