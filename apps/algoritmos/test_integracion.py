"""Los ordenamientos hechos a mano están conectados a las pantallas y ordenan bien (con empates)."""
import re

from django.test import TestCase
from django.urls import reverse

from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.inventario.models import Inventario
from apps.usuarios.models import Sede, Usuario

PWD = "Str0ng-Pass#2026"


def orden_en_pagina(html, nombres):
    """Devuelve los nombres en el orden en que aparecen en el HTML."""
    return sorted(nombres, key=lambda n: html.index(n))


class OrdenEnPantallasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sede = Sede.objects.create(nombre="Zona T", direccion="x")
        cls.admin = Usuario.objects.create_user(username="admin", password=PWD, nombre="Zeta Admin", rol="ADMIN", sede=cls.sede)
        cls.mesero = Usuario.objects.create_user(username="mesero1", password=PWD, nombre="Beto Mesero", rol="WAITER", sede=cls.sede)
        Usuario.objects.create_user(username="cajero1", password=PWD, nombre="Ana Cajera", rol="CASHIER", sede=cls.sede)
        tipo, prov = TipoProducto.objects.create(nombre="T"), Proveedor.objects.create(nombre="P", contacto="c")
        datos = [("Mojito", 18000, 3), ("Corona", 5000, 10), ("Aguila", 5000, 10), ("Ron", 30000, 0)]
        for nombre, precio, cantidad in datos:
            producto = Producto.objects.create(nombre=nombre, valor_compra=1, valor_venta=precio, tipo_producto=tipo, proveedor=prov)
            Inventario.objects.create(producto=producto, sede=cls.sede, cantidad=cantidad)

    def test_products_by_price_then_name(self):  # selección
        self.client.force_login(self.admin)
        html = self.client.get(reverse("catalogo:producto_list")).content.decode()
        self.assertEqual(orden_en_pagina(html, ["Mojito", "Corona", "Aguila", "Ron"]), ["Aguila", "Corona", "Mojito", "Ron"])

    def test_inventory_by_quantity_then_name(self):  # inserción
        self.client.force_login(self.mesero)
        html = self.client.get(reverse("inventario:inventario_list")).content.decode()
        self.assertEqual(orden_en_pagina(html, ["Mojito", "Corona", "Aguila", "Ron"]), ["Ron", "Mojito", "Aguila", "Corona"])

    def test_users_by_name(self):  # burbuja
        self.client.force_login(self.admin)
        html = self.client.get(reverse("usuarios:usuario_list")).content.decode()
        tabla = html[html.index("<tbody>"):html.index("</tbody>")]
        nombres = re.findall(r"<td>(Ana Cajera|Beto Mesero|Zeta Admin)</td>", tabla)
        self.assertEqual(nombres, ["Ana Cajera", "Beto Mesero", "Zeta Admin"])
