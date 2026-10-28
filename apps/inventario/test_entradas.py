"""HU043 — Registrar entrada de inventario (el administrador anota la mercancía que llega a cada sede)."""
from django.test import Client, TestCase
from django.urls import reverse

from apps.auditoria.models import Bitacora
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.usuarios.models import Sede, Usuario

from .models import Inventario

PWD = "Str0ng-Pass#2026"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.zona_t = Sede.objects.create(nombre="Zona T", direccion="x")
        cls.galerias = Sede.objects.create(nombre="Galerias", direccion="y")
        cls.admin = Usuario.objects.create_user(username="admin", password=PWD, nombre="Admin", rol="ADMIN", sede=cls.zona_t)
        cls.mesero = Usuario.objects.create_user(username="mesero1", password=PWD, nombre="Maria", rol="WAITER", sede=cls.zona_t)
        cls.cajero = Usuario.objects.create_user(username="cajero1", password=PWD, nombre="Carlos", rol="CASHIER", sede=cls.zona_t)
        tipo, prov = TipoProducto.objects.create(nombre="Cervezas"), Proveedor.objects.create(nombre="Bavaria", contacto="1")
        cls.aguila = Producto.objects.create(nombre="Aguila", valor_compra=1, valor_venta=2, tipo_producto=tipo, proveedor=prov)
        cls.corona = Producto.objects.create(nombre="Corona", valor_compra=1, valor_venta=2, tipo_producto=tipo, proveedor=prov)
        cls.viejo = Producto.objects.create(nombre="Descontinuado", valor_compra=1, valor_venta=2, tipo_producto=tipo, proveedor=prov, activo=False)

    def setUp(self):
        self.client.force_login(self.admin)

    def post(self, lineas, sede=None, **kw):
        datos = {"sede": (sede or self.zona_t).pk}
        datos.update({f"qty_{producto.pk}": valor for producto, valor in lineas.items()})
        return self.client.post(reverse("inventario:stock_receive"), datos, **kw)

    def stock(self, producto, sede=None):
        fila = Inventario.objects.filter(producto=producto, sede=sede or self.zona_t).first()
        return fila.cantidad if fila else None


class AccessTests(Base):
    URLS = ["inventario:stock_list", "inventario:stock_receive"]

    def test_admin_reaches_both_screens(self):
        for name in self.URLS:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_waiter_and_cashier_forbidden(self):
        # El mesero no puede acceder a la gestión de existencias.
        waiter_client = Client()
        waiter_client.force_login(self.mesero)

        for name in self.URLS:
            self.assertEqual(
                waiter_client.get(reverse(name)).status_code,
                403,
                (self.mesero.username, name),
            )

        self.assertEqual(
            waiter_client.post(
                reverse("inventario:stock_receive"),
                {"sede": self.zona_t.pk, f"qty_{self.aguila.pk}": "5"},
            ).status_code,
            403,
        )

        # Fase 8.7: el cajero puede consultar y recibir stock en su sede.
        cashier_client = Client()
        cashier_client.force_login(self.cajero)

        for name in self.URLS:
            self.assertEqual(
                cashier_client.get(reverse(name)).status_code,
                200,
                (self.cajero.username, name),
            )

        # La consulta no debe modificar el inventario.
        self.assertIsNone(self.stock(self.aguila))

    def test_anonymous_goes_to_login(self):
        self.assertEqual(Client().get(reverse("inventario:stock_receive")).status_code, 302)

    def test_blocked_while_admin_acts_as_waiter(self):
        self.client.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": self.zona_t.pk})
        for name in self.URLS:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)


class ReceiveTests(Base):
    def test_first_delivery_creates_the_row_and_next_ones_add_up(self):
        self.post({self.aguila: "30"})
        self.assertEqual(self.stock(self.aguila), 30)
        self.post({self.aguila: "12"})
        self.assertEqual(self.stock(self.aguila), 42)
        self.assertEqual(Inventario.objects.filter(producto=self.aguila, sede=self.zona_t).count(), 1)

    def test_several_products_in_one_delivery(self):
        resp = self.post({self.aguila: "30", self.corona: "24"}, follow=True)
        self.assertEqual((self.stock(self.aguila), self.stock(self.corona)), (30, 24))
        self.assertContains(resp, "Stock received at Zona T")
        self.assertContains(resp, "Aguila +30")

    def test_each_site_has_its_own_stock(self):
        self.post({self.aguila: "30"}, sede=self.zona_t)
        self.post({self.aguila: "10"}, sede=self.galerias)
        self.assertEqual((self.stock(self.aguila, self.zona_t), self.stock(self.aguila, self.galerias)), (30, 10))

    def test_blank_and_zero_lines_are_ignored(self):
        self.post({self.aguila: "5", self.corona: "0"})
        self.assertEqual(self.stock(self.aguila), 5)
        self.assertIsNone(self.stock(self.corona))

    def test_every_entry_is_audited_with_before_and_after(self):
        self.post({self.aguila: "30"})
        self.post({self.aguila: "12"})
        detalles = list(Bitacora.objects.filter(accion="STOCK_IN").order_by("id").values_list("detalle", flat=True))
        self.assertEqual(detalles, ["Aguila +30 at Zona T (0 -> 30)", "Aguila +12 at Zona T (30 -> 42)"])
        self.assertTrue(Bitacora.objects.filter(accion="STOCK_IN", usuario=self.admin).exists())

    def test_waiter_sees_the_new_stock(self):
        self.post({self.aguila: "30"})
        c = Client()
        c.force_login(self.mesero)
        resp = c.get(reverse("inventario:inventario_list"))
        self.assertContains(resp, "Aguila")
        self.assertContains(resp, "30")

    def test_redirects_to_the_stock_of_that_site(self):
        resp = self.post({self.aguila: "1"}, sede=self.galerias)
        self.assertRedirects(resp, reverse("inventario:stock_list") + f"?sede={self.galerias.pk}")


class ValidationTests(Base):
    def assert_nothing_changed(self):
        self.assertEqual(Inventario.objects.count(), 0)
        self.assertFalse(Bitacora.objects.filter(accion="STOCK_IN").exists())

    def test_rejects_negative_decimal_and_text(self):
        for malo in ("-5", "2.5", "abc", "1e3", "²"):
            resp = self.post({self.aguila: malo})
            self.assertContains(resp, "enter a whole number of units")
        self.assert_nothing_changed()

    def test_rejects_absurdly_large_entries(self):
        self.assertContains(self.post({self.aguila: "100001"}), "maximum per delivery")
        self.assert_nothing_changed()
        self.post({self.aguila: "100000"})
        self.assertEqual(self.stock(self.aguila), 100000)

    def test_requires_at_least_one_quantity(self):
        self.assertContains(self.post({self.aguila: "", self.corona: "0"}), "at least one product")
        self.assert_nothing_changed()

    def test_all_or_nothing(self):
        self.post({self.aguila: "30", self.corona: "abc"})
        self.assert_nothing_changed()

    def test_typed_values_are_kept_when_there_is_an_error(self):
        resp = self.post({self.aguila: "30", self.corona: "abc"})
        html = resp.content.decode()
        self.assertIn('value="30"', html)
        self.assertIn('value="abc"', html)

    def test_inactive_products_are_not_listed_or_accepted(self):
        resp = self.client.get(reverse("inventario:stock_receive"))
        self.assertNotContains(resp, "Descontinuado")
        self.post({self.viejo: "9"})
        self.assertIsNone(self.stock(self.viejo))

    def test_unknown_inactive_or_weird_site_is_rejected(self):
        self.galerias.activo = False
        self.galerias.save()
        for sede in ("9999", "abc", "²", str(self.galerias.pk)):
            resp = self.client.post(reverse("inventario:stock_receive"), {"sede": sede, f"qty_{self.aguila.pk}": "5"})
            self.assertEqual(resp.status_code, 302, sede)
        self.assert_nothing_changed()
        self.assertEqual(self.client.get(reverse("inventario:stock_list") + "?sede=²").status_code, 200)


class StockListTests(Base):
    def test_shows_the_chosen_site_and_not_the_others(self):
        Inventario.objects.create(producto=self.aguila, sede=self.zona_t, cantidad=11)
        Inventario.objects.create(producto=self.aguila, sede=self.galerias, cantidad=77)
        html = self.client.get(reverse("inventario:stock_list") + f"?sede={self.galerias.pk}").content.decode()
        self.assertIn("Stock at Galerias", html)
        self.assertIn(">77<", html)
        self.assertNotIn(">11<", html)

    def test_defaults_to_the_admins_own_site(self):
        resp = self.client.get(reverse("inventario:stock_list"))
        self.assertEqual(resp.context["sede"], self.zona_t)

    def test_products_never_received_show_as_out_of_stock(self):
        resp = self.client.get(reverse("inventario:stock_list"))
        nombres = [f["producto"].nombre for f in resp.context["filas"]]
        self.assertEqual(nombres, ["Aguila", "Corona"])  # por nombre, solo activos
        self.assertContains(resp, "OUT OF STOCK", count=2)

    def test_site_selector_offers_only_active_sites(self):
        self.galerias.activo = False
        self.galerias.save()
        resp = self.client.get(reverse("inventario:stock_list"))
        self.assertEqual([s.nombre for s in resp.context["sedes"]], ["Zona T"])

    def test_search_filters_products(self):
        resp = self.client.get(reverse("inventario:stock_list") + "?q=coro")
        self.assertEqual([f["producto"].nombre for f in resp.context["filas"]], ["Corona"])
        self.assertContains(self.client.get(reverse("inventario:stock_list") + "?q=zzz"), "No results found")


class MenuTests(Base):
    def test_admin_inventory_entry_opens_the_stock_screen_and_stays_highlighted(self):
        resp = self.client.get(reverse("inventario:stock_receive"))
        entrada = [i for i in resp.context["nav_items"] if i["label"] == "Inventory"][0]
        self.assertEqual(entrada["url"], reverse("inventario:stock_list"))
        self.assertTrue(entrada.get("active"))
