from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Sede, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("CUADRA", {"fields": ("nombre", "rol", "sede")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("CUADRA", {"fields": ("nombre", "rol", "sede")}),)
    list_display = ("username", "nombre", "rol", "sede", "is_active")


admin.site.register(Sede)
