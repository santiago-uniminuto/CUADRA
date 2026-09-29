from django.contrib import admin

from .models import DetallePedido, Mesa, Pedido

admin.site.register([Mesa, Pedido, DetallePedido])
