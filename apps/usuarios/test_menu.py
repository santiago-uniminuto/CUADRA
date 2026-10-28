"""Menú de navegación por rol y diseño base."""
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse

from .models import Sede, Usuario

PWD = "Str0ng-Pass#2026"
ADMIN_MENU = ["Dashboard", "Users", "Sites", "Activity log", "Products", "Suppliers", "Product types", "Inventory", "Tables", "Consolidated report", "Sales report", "Inventory report"]


def items(resp):
    return [(i["label"], i.get("active", False)) for i in resp.context["nav_items"]]


class MenuTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sede = Sede.objects.create(nombre="Zona T", direccion="x")
        for username, rol in [("admin", "ADMIN"), ("mesero1", "WAITER"), ("cajero1", "CASHIER")]:
            setattr(cls, username, Usuario.objects.create_user(username=username, password=PWD, nombre=username, rol=rol, sede=cls.sede))

    def client_for(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_admin_menu(self):
        resp = self.client_for(self.admin).get(reverse("usuarios:usuario_list"))
        self.assertEqual([label for label, _ in items(resp)], ADMIN_MENU)

    def test_waiter_and_cashier_menus(self):
        resp = self.client_for(self.mesero1).get(reverse("inventario:inventario_list"))
        self.assertEqual([label for label, _ in items(resp)], ["Inventory", "Tables & orders"])
        resp = self.client_for(self.cajero1).get(reverse("pagos:queue"))
        self.assertEqual([label for label, _ in items(resp)], ["Payments", "Inventory", "Sales report", "Inventory report"])

    def test_menu_never_offers_pages_the_role_cannot_open(self):
        for user in (self.admin, self.mesero1):
            c = self.client_for(user)
            resp = c.get(reverse("inventario:inventario_list"))
            for item in resp.context["nav_items"]:
                self.assertEqual(c.get(item["url"]).status_code, 200, (user.username, item["label"]))

    def test_active_entry_is_the_most_specific_one(self):
        c = self.client_for(self.admin)
        self.assertEqual([l for l, a in items(c.get(reverse("usuarios:sede_list"))) if a], ["Sites"])
        self.assertEqual([l for l, a in items(c.get(reverse("usuarios:usuario_list"))) if a], ["Users"])
        self.assertEqual([l for l, a in items(c.get(reverse("usuarios:usuario_create"))) if a], ["Users"])
        self.assertEqual([l for l, a in items(c.get(reverse("catalogo:proveedor_list"))) if a], ["Suppliers"])

    def test_admin_acting_as_waiter_sees_the_waiter_menu(self):
        c = self.client_for(self.admin)
        c.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": self.sede.pk})
        resp = c.get(reverse("inventario:inventario_list"))
        self.assertEqual([label for label, _ in items(resp)], ["Inventory", "Tables & orders"])
        # Acting Mode intentionally prevents switching roles directly.
        # Return to Admin first, then enter Cashier mode.
        c.post(reverse("usuarios:return_to_admin"))
        resp = c.post(reverse("usuarios:act_as"), {"rol": "CASHIER", "sede": self.sede.pk})
        self.assertEqual(resp.status_code, 302)
        resp = c.get(reverse("pagos:queue"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([label for label, _ in items(resp)], ["Payments", "Inventory", "Sales report", "Inventory report"])
        c.post(reverse("usuarios:return_to_admin"))
        self.assertEqual([l for l, _ in items(c.get(reverse("usuarios:usuario_list")))], ADMIN_MENU)

    def test_login_page_has_no_menu_and_assets_are_local(self):
        resp = Client().get(reverse("autenticacion:login"))
        self.assertNotIn("nav_items", resp.context or {})
        html = resp.content.decode()
        self.assertIn("vendor/bootstrap/bootstrap.min.css", html)
        self.assertNotIn("cdn.jsdelivr.net", html)  # funciona sin internet en la red local

    def test_page_is_responsive(self):
        html = self.client_for(self.admin).get(reverse("usuarios:usuario_list")).content.decode()
        self.assertIn('name="viewport"', html)
        self.assertIn('data-bs-toggle="offcanvas"', html)  # el menú lateral del admin se oculta en pantallas angostas

    def test_static_files_really_exist(self):
        """No basta con que el HTML los nombre: los archivos tienen que estar en el proyecto."""
        for ruta in ("css/cuadra.css", "vendor/bootstrap/bootstrap.min.css", "vendor/bootstrap/bootstrap.bundle.min.js"):
            self.assertTrue(finders.find(ruta), f"Falta el archivo estático {ruta}")
