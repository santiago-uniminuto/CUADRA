from django.contrib import admin

from .models import Bitacora


@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    """Solo lectura: la bitácora se inserta, nunca se edita ni se borra (ni desde el panel técnico)."""

    list_display = ("fecha", "usuario", "accion", "entidad", "detalle")
    list_filter = ("accion", "entidad")
    search_fields = ("detalle", "usuario__username")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
