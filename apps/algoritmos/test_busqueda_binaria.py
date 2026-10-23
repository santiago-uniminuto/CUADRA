"""Pruebas unitarias e integración de búsqueda binaria por código de producto."""
from django.test import TestCase
from django.urls import reverse

from apps.algoritmos.ordenamiento import binary_search
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.usuarios.models import Sede, Usuario


class BinarySearchTests(TestCase):
    def test_existing_missing_and_boundaries(self):
        values = [1, 3, 5, 9, 12]
        self.assertEqual(binary_search(values, 1), 1)
        self.assertEqual(binary_search(values, 12), 12)
        self.assertEqual(binary_search(values, 5), 5)
        self.assertIsNone(binary_search(values, 8))
        self.assertIsNone(binary_search([], 1))

    def test_search_objects_does_not_modify_input(self):
        items = [{"code": 2}, {"code": 4}, {"code": 6}]
        found = binary_search(items, 4, key=lambda x: x["code"])
        self.assertIs(found, items[1])
        self.assertEqual([x["code"] for x in items], [2, 4, 6])

    @classmethod
    def setUpTestData(cls):
        sede = Sede.objects.create(nombre="Binary Site", direccion="x")
        cls.admin = Usuario.objects.create_user(
            username="binaryadmin", password="Str0ng-Pass#2026",
            nombre="Admin", rol="ADMIN", sede=sede)
        cls.waiter = Usuario.objects.create_user(
            username="binarywaiter", password="Str0ng-Pass#2026",
            nombre="Waiter", rol="WAITER", sede=sede)
        tipo = TipoProducto.objects.create(nombre="Binary Type")
        supplier = Proveedor.objects.create(nombre="Binary Supplier", contacto="x")
        cls.first = Producto.objects.create(nombre="Aguila", valor_compra=100,
            valor_venta=200, tipo_producto=tipo, proveedor=supplier)
        cls.second = Producto.objects.create(nombre="Corona", valor_compra=100,
            valor_venta=300, tipo_producto=tipo, proveedor=supplier)

    def test_catalog_exact_code_and_missing_code(self):
        self.client.force_login(self.admin)
        url = reverse("catalogo:producto_list")
        response = self.client.get(url, {"q": f"#{self.second.pk}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p.pk for p in response.context["productos"]], [self.second.pk])
        response = self.client.get(url, {"q": "#999999999"})
        self.assertEqual(list(response.context["productos"]), [])

    def test_catalog_name_search_still_works(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("catalogo:producto_list"), {"q": "agui"})
        self.assertEqual([p.pk for p in response.context["productos"]], [self.first.pk])

    def test_waiter_cannot_search_admin_catalog(self):
        self.client.force_login(self.waiter)
        response = self.client.get(reverse("catalogo:producto_list"), {"q": f"#{self.first.pk}"})
        self.assertNotEqual(response.status_code, 200)
