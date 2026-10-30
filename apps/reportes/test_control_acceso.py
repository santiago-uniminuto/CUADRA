"""
Regression tests for access control on every routed view (OWASP A01).

Closing audit finding: reportes:general_export had no @role_required and
returned the consolidated sales and inventory workbook to anonymous users and
to waiters/cashiers. These tests sweep all application URLs so that a view
added without its decorator is detected automatically.
"""
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.usuarios.models import Sede, Usuario

# Public by design: the login form itself and the logout entry point
# (which redirects anonymous users to the login screen).
PUBLIC = {"autenticacion:login", "autenticacion:logout"}


def _app_routes():
    """(name, path) of every named CUADRA route, filling int parameters with 1."""
    routes = []

    def walk(patterns, prefix="", namespace=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                ns = f"{namespace}{p.namespace}:" if p.namespace else namespace
                walk(p.url_patterns, prefix + str(p.pattern), ns)
            elif isinstance(p, URLPattern) and p.name:
                name = f"{namespace}{p.name}"
                if name.startswith("admin:") or not namespace:
                    continue
                kwargs = {k: 1 for k in p.pattern.converters}
                routes.append((name, reverse(name, kwargs=kwargs)))

    walk(get_resolver().url_patterns)
    return routes


class AnonymousAccessTests(TestCase):
    def test_every_protected_route_redirects_anonymous_users_to_login(self):
        routes = _app_routes()
        self.assertGreater(len(routes), 30)
        for name, url in routes:
            if name in PUBLIC:
                continue
            with self.subTest(route=name):
                response = self.client.get(url)
                # 405 = POST-only endpoint; it never executes on GET.
                self.assertIn(response.status_code, (302, 405), url)
                if response.status_code == 302:
                    self.assertIn("/login/", response["Location"])


class GeneralExportAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sede = Sede.objects.create(nombre="Zona T", direccion="Bogota")
        cls.waiter = Usuario.objects.create_user("w1", password="Pass-2026-x", nombre="W", rol="WAITER", sede=cls.sede)
        cls.cashier = Usuario.objects.create_user("c1", password="Pass-2026-x", nombre="C", rol="CASHIER", sede=cls.sede)
        cls.admin = Usuario.objects.create_user("a1", password="Pass-2026-x", nombre="A", rol="ADMIN", sede=cls.sede)

    def test_anonymous_cannot_download_consolidated_export(self):
        response = self.client.get(reverse("reportes:general_export"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("spreadsheetml", response.get("Content-Type", ""))

    def test_waiter_and_cashier_cannot_download_consolidated_export(self):
        for user in (self.waiter, self.cashier):
            with self.subTest(rol=user.rol):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse("reportes:general_export")).status_code, 403)

    def test_admin_acting_as_cashier_cannot_download_consolidated_export(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("usuarios:act_as"), {"rol": "CASHIER", "sede": self.sede.pk})
        self.assertEqual(self.client.get(reverse("reportes:general_export")).status_code, 403)

    def test_admin_downloads_consolidated_export(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reportes:general_export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
