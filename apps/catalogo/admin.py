from django.contrib import admin

from .models import Producto, Proveedor, TipoProducto

admin.site.register([TipoProducto, Proveedor, Producto])
