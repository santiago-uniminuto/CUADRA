"""Dashboard del administrador y las dos interfaces (panel de gestión / punto de venta)."""
from django.test import Client, TestCase
from django.urls import reverse

from apps.auditoria.models import Bitacora
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.usuarios.models import Sede, Usuario

PWD = "Str0ng-Pass#2026"


class DashboardBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.zona_t = Sede.objects.create(nombre="Zona T", direccion="x")
        cls.galerias = Sede.objects.create(nombre="Galerias", direccion="y")
        cls.admin = Usuario.objects.create_user(username="admin", password=PWD, nombre="Laura Admin", rol="ADMIN", sede=cls.zona_t)
        cls.mesero = Usuario.objects.create_user(username="mesero1", password=PWD, nombre="Maria", rol="WAITER", sede=cls.zona_t)
        cls.cajero = Usuario.objects.create_user(username="cajero1", password=PWD, nombre="Carlos", rol="CASHIER", sede=cls.galerias)
        Usuario.objects.create_user(username="viejo", password=PWD, nombre="Inactivo", rol="WAITER", sede=cls.galerias, is_active=False)

    def get(self, user, name):
        c = Client()
        c.force_login(user)
        return c.get(reverse(name))


class DashboardTests(DashboardBase):
    def test_welcome_message_uses_the_name(self):
        resp = self.get(self.admin, "reportes:dashboard")
        self.assertContains(resp, "Welcome back, Laura Admin")

    def test_cards_count_active_and_inactive(self):
        resp = self.get(self.admin, "reportes:dashboard")
        tarjetas = {t["label"]: t for t in resp.context["tarjetas"]}
        self.assertEqual(tarjetas["Users"]["value"], 3)
        self.assertEqual(tarjetas["Users"]["sub"], "1 inactive")
        self.assertEqual(tarjetas["Sites"]["value"], 2)

    def test_products_cards_follow_the_catalog(self):
        tipo = TipoProducto.objects.create(nombre="T")
        prov = Proveedor.objects.create(nombre="P", contacto="c")
        Producto.objects.create(nombre="A", valor_compra=1, valor_venta=2, tipo_producto=tipo, proveedor=prov)
        Producto.objects.create(nombre="B", valor_compra=1, valor_venta=2, tipo_producto=tipo, proveedor=prov, activo=False)
        tarjetas = {t["label"]: t for t in self.get(self.admin, "reportes:dashboard").context["tarjetas"]}
        self.assertEqual((tarjetas["Products"]["value"], tarjetas["Products"]["sub"]), (1, "1 inactive"))

    def test_team_by_site_counts_only_active_users(self):
        por_sede = {s.nombre: s for s in self.get(self.admin, "reportes:dashboard").context["por_sede"]}
        self.assertEqual((por_sede["Zona T"].meseros, por_sede["Zona T"].admins, por_sede["Zona T"].total), (1, 1, 2))
        self.assertEqual((por_sede["Galerias"].cajeros, por_sede["Galerias"].meseros, por_sede["Galerias"].total), (1, 0, 1))

    def test_recent_activity_is_listed_newest_first(self):
        Bitacora.objects.create(usuario=self.admin, accion="CREATE", entidad="Usuario", detalle="primero")
        Bitacora.objects.create(usuario=self.admin, accion="DEACTIVATE", entidad="Producto", detalle="segundo")
        html = self.get(self.admin, "reportes:dashboard").content.decode()
        self.assertLess(html.index("segundo"), html.index("primero"))

    def test_no_stock_alerts_are_shown(self):
        # "No hay alertas de stock mínimo" está fuera de alcance.
        html = self.get(self.admin, "reportes:dashboard").content.decode().lower()
        self.assertNotIn("low stock", html)

    def test_only_admin_can_open_it(self):
        self.assertEqual(self.get(self.mesero, "reportes:dashboard").status_code, 403)
        self.assertEqual(self.get(self.cajero, "reportes:dashboard").status_code, 403)
        self.assertEqual(Client().get(reverse("reportes:dashboard")).status_code, 302)

    def test_blocked_while_admin_acts_as_waiter(self):
        c = Client()
        c.force_login(self.admin)
        c.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": self.zona_t.pk})
        self.assertEqual(c.get(reverse("reportes:dashboard")).status_code, 403)
        c.post(reverse("usuarios:return_to_admin"))
        self.assertEqual(c.get(reverse("reportes:dashboard")).status_code, 200)


class LayoutTests(DashboardBase):
    def test_admin_gets_the_management_panel(self):
        html = self.get(self.admin, "usuarios:usuario_list").content.decode()
        self.assertIn("layout-admin", html)
        self.assertIn('id="sidebar"', html)
        self.assertNotIn('data-bs-theme="dark"', html)

    def test_waiter_and_cashier_get_the_pos_interface(self):
        for user, name in [(self.mesero, "inventario:inventario_list"), (self.cajero, "pagos:queue")]:
            html = self.get(user, name).content.decode()
            self.assertIn("layout-pos", html, user.username)
            self.assertIn('data-bs-theme="dark"', html)
            self.assertNotIn('id="sidebar"', html)
            self.assertIn("pos-tabs", html)

    def test_pos_shows_the_site_being_served(self):
        html = self.get(self.mesero, "inventario:inventario_list").content.decode()
        self.assertIn('class="pos-site">Zona T<', html)

    def test_admin_acting_gets_the_pos_interface_and_a_way_back(self):
        c = Client()
        c.force_login(self.admin)
        c.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": self.galerias.pk})
        html = c.get(reverse("inventario:inventario_list")).content.decode()
        self.assertIn("layout-pos", html)
        self.assertIn('class="pos-site">Galerias<', html)
        self.assertIn("Return to Admin", html)

    def test_login_page_is_the_plain_guest_layout(self):
        html = Client().get(reverse("autenticacion:login")).content.decode()
        self.assertIn("layout-guest", html)
        self.assertNotIn('id="sidebar"', html)
        self.assertNotIn("pos-topbar", html)
