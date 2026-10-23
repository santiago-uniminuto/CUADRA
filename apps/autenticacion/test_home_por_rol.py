"""HU001, escenario 1 — cada rol llega a su pantalla principal."""
from django.test import Client, TestCase
from django.urls import reverse

from apps.usuarios.models import Sede, Usuario

PWD = "Str0ng-Pass#2026"


class HomePorRolTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sede = Sede.objects.create(nombre="Zona T", direccion="x")
        for username, rol in [("admin", "ADMIN"), ("mesero1", "WAITER"), ("cajero1", "CASHIER")]:
            Usuario.objects.create_user(username=username, password=PWD, nombre=username, rol=rol, sede=sede)

    def login(self, username):
        c = Client()
        c.force_login(Usuario.objects.get(username=username))
        return c

    def test_admin_goes_to_dashboard(self):
        resp = self.login("admin").get(reverse("autenticacion:home"))
        self.assertRedirects(resp, reverse("reportes:dashboard"))

    def test_waiter_goes_to_inventory(self):
        resp = self.login("mesero1").get(reverse("autenticacion:home"))
        self.assertRedirects(resp, reverse("inventario:inventario_list"))

    def test_cashier_goes_directly_to_payments(self):
        resp = self.login("cajero1").get(reverse("autenticacion:home"))
        self.assertRedirects(resp, reverse("pagos:queue"))

    def test_anonymous_goes_to_login(self):
        resp = Client().get(reverse("autenticacion:home"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_real_login_lands_on_the_role_screen(self):
        c = Client()
        resp = c.post(reverse("autenticacion:login"), {"username": "mesero1", "password": PWD}, follow=True)
        self.assertEqual(resp.redirect_chain[-1][0], reverse("inventario:inventario_list"))
        resp = Client().post(reverse("autenticacion:login"), {"username": "admin", "password": PWD}, follow=True)
        self.assertEqual(resp.redirect_chain[-1][0], reverse("reportes:dashboard"))

    def test_real_cashier_login_lands_on_payments(self):
        c = Client()
        resp = c.post(reverse("autenticacion:login"), {"username": "cajero1", "password": PWD}, follow=True)
        self.assertEqual(resp.redirect_chain[-1][0], reverse("pagos:queue"))

    def test_admin_acting_as_cashier_is_sent_to_payments(self):
        c = self.login("admin")
        sede = Sede.objects.get()
        resp = c.post(reverse("usuarios:act_as"), {"rol": "CASHIER", "sede": sede.pk}, follow=True)
        self.assertEqual(resp.redirect_chain[-1][0], reverse("pagos:queue"))

    def test_admin_acting_as_waiter_is_sent_to_inventory(self):
        c = self.login("admin")
        sede = Sede.objects.get()
        c.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": sede.pk})
        resp = c.get(reverse("autenticacion:home"))
        self.assertRedirects(resp, reverse("inventario:inventario_list"))
