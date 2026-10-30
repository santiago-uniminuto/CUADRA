"""
HU002, escenario 1: la pantalla debe cerrarse sola tras 3 minutos sin actividad.

El servidor ya cerraba la sesión en la siguiente petición (InactivityTimeoutMiddleware).
Cierre de auditoría: base.html programa una nueva petición GET al cumplirse el plazo,
para que el aviso aparezca aunque el usuario no vuelva a hacer clic.
"""
import time

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.auditoria.models import ACCIONES, Bitacora
from apps.usuarios.models import Sede, Usuario


class InactivityScreenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sede = Sede.objects.create(nombre="Zona T", direccion="Bogota")
        cls.waiter = Usuario.objects.create_user("w1", password="Pass-2026-x", nombre="W", rol="WAITER", sede=cls.sede)

    def test_authenticated_pages_schedule_the_inactivity_reload(self):
        self.client.force_login(self.waiter)
        response = self.client.get(reverse("pedidos:tables"))
        self.assertContains(response, "var seconds = 180;")
        self.assertContains(response, "window.location.replace")

    @override_settings(SESSION_INACTIVITY_TIMEOUT=60)
    def test_reload_uses_the_configured_timeout(self):
        self.client.force_login(self.waiter)
        self.assertContains(self.client.get(reverse("pedidos:tables")), "var seconds = 60;")

    def test_login_page_has_no_inactivity_reload(self):
        self.assertNotContains(self.client.get(reverse("autenticacion:login")), "window.location.replace")

    def test_reload_after_timeout_closes_session_and_shows_notice(self):
        self.client.force_login(self.waiter)
        self.client.get(reverse("pedidos:tables"))
        session = self.client.session
        session["last_activity"] = time.time() - 181
        session.save()
        response = self.client.get(reverse("pedidos:tables"), follow=True)
        self.assertContains(response, "Your session was closed due to inactivity")
        self.assertTrue(Bitacora.objects.filter(usuario=self.waiter, accion="SESSION_EXPIRED").exists())


class AuditCatalogTests(TestCase):
    def test_table_actions_have_readable_labels(self):
        for code in ("TABLE_CREATE", "TABLE_ENABLE", "TABLE_DISABLE", "TABLE_RELEASE"):
            with self.subTest(code=code):
                self.assertIn(code, ACCIONES)
                self.assertNotEqual(Bitacora(accion=code).accion_legible, code)
