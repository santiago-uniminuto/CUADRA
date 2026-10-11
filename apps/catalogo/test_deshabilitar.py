"""Deshabilitar / reactivar productos, proveedores y tipos de producto (nada se borra)."""
from django.test import Client, TestCase
from django.urls import reverse

from apps.auditoria.models import Bitacora
from apps.inventario.models import Inventario
from apps.usuarios.models import Sede, Usuario

from .forms import ProductoForm
from .models import Producto, Proveedor, TipoProducto

PWD = "Str0ng-Pass#2026"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sede = Sede.objects.create(nombre="Zona T", direccion="x")
        cls.admin = Usuario.objects.create_user(username="admin", password=PWD, nombre="Admin", rol="ADMIN", sede=cls.sede)
        cls.mesero = Usuario.objects.create_user(username="mesero1", password=PWD, nombre="Maria", rol="WAITER", sede=cls.sede)
        cls.tipo = TipoProducto.objects.create(nombre="Cervezas")
        cls.prov = Proveedor.objects.create(nombre="Bavaria", contacto="1")
        cls.corona = Producto.objects.create(nombre="Corona", valor_compra=1, valor_venta=2, tipo_producto=cls.tipo, proveedor=cls.prov)
        Inventario.objects.create(producto=cls.corona, sede=cls.sede, cantidad=5)

    def setUp(self):
        self.client.force_login(self.admin)


class ProductoToggleTests(Base):
    def url(self):
        return reverse("catalogo:producto_toggle", args=[self.corona.pk])

    def test_get_asks_for_confirmation_and_changes_nothing(self):
        resp = self.client.get(self.url())
        self.assertContains(resp, "Are you sure you want to deactivate")
        self.corona.refresh_from_db()
        self.assertTrue(self.corona.activo)

    def test_deactivate_then_reactivate(self):
        self.client.post(self.url())
        self.corona.refresh_from_db()
        self.assertFalse(self.corona.activo)
        self.assertContains(self.client.get(self.url()), "Are you sure you want to reactivate")
        self.client.post(self.url())
        self.corona.refresh_from_db()
        self.assertTrue(self.corona.activo)
        self.assertEqual(Bitacora.objects.filter(entidad="Producto", entidad_id=self.corona.pk).count(), 2)

    def test_inactive_product_is_not_sold_but_history_stays(self):
        self.client.post(self.url())
        waiter = Client()
        waiter.force_login(self.mesero)
        self.assertNotContains(waiter.get(reverse("inventario:inventario_list")), "Corona")
        self.assertTrue(Inventario.objects.filter(producto=self.corona).exists())  # no se borra nada
        resp = self.client.get(reverse("catalogo:producto_list"))
        self.assertContains(resp, "Corona")
        self.assertContains(resp, "REACTIVATE")

    def test_non_admin_forbidden(self):
        waiter = Client()
        waiter.force_login(self.mesero)
        self.assertEqual(waiter.get(self.url()).status_code, 403)
        self.assertEqual(waiter.post(self.url()).status_code, 403)
        self.corona.refresh_from_db()
        self.assertTrue(self.corona.activo)

    def test_blocked_while_admin_acts_as_waiter(self):
        self.client.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": self.sede.pk})
        self.assertEqual(self.client.post(self.url()).status_code, 403)


class ProveedorTipoToggleTests(Base):
    def test_deactivated_supplier_and_type_are_not_offered_for_new_products(self):
        self.client.post(reverse("catalogo:proveedor_toggle", args=[self.prov.pk]))
        self.client.post(reverse("catalogo:tipoproducto_toggle", args=[self.tipo.pk]))
        form = ProductoForm()
        self.assertNotIn(self.prov, form.fields["proveedor"].queryset)
        self.assertNotIn(self.tipo, form.fields["tipo_producto"].queryset)

    def test_existing_product_keeps_its_inactive_supplier_when_edited(self):
        self.client.post(reverse("catalogo:proveedor_toggle", args=[self.prov.pk]))
        form = ProductoForm(instance=self.corona)
        self.assertIn(self.prov, form.fields["proveedor"].queryset)
        self.corona.refresh_from_db()
        self.assertTrue(self.corona.activo)  # el producto sigue a la venta

    def test_confirmation_warns_how_many_active_products_use_it(self):
        resp = self.client.get(reverse("catalogo:proveedor_toggle", args=[self.prov.pk]))
        self.assertContains(resp, "1 active product(s) use this supplier")

    def test_reactivate_supplier_offers_it_again(self):
        url = reverse("catalogo:proveedor_toggle", args=[self.prov.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertIn(self.prov, ProductoForm().fields["proveedor"].queryset)

    def test_lists_show_status_and_buttons(self):
        self.client.post(reverse("catalogo:tipoproducto_toggle", args=[self.tipo.pk]))
        resp = self.client.get(reverse("catalogo:tipoproducto_list"))
        self.assertContains(resp, "Inactive")
        self.assertContains(resp, "REACTIVATE")
        self.assertContains(self.client.get(reverse("catalogo:proveedor_list")), "DEACTIVATE")
