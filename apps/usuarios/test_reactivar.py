"""HU033 — Reactivar usuario (escenarios 1, 2 y 3 del Gherkin)."""
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Bitacora

from .tests import PWD, BaseUsuariosTest


class ReactivateTests(BaseUsuariosTest):
    def setUp(self):
        super().setUp()
        self.mesero.is_active = False
        self.mesero.save()

    def url(self):
        return reverse("usuarios:usuario_reactivate", args=[self.mesero.pk])

    def test_get_asks_confirmation_and_changes_nothing(self):  # escenario 2 y 3 (cancelar)
        resp = self.client.get(self.url())
        self.assertContains(resp, "Are you sure you want to reactivate")
        self.mesero.refresh_from_db()
        self.assertFalse(self.mesero.is_active)  # sigue Inactive

    def test_confirm_reactivates_and_allows_login(self):  # escenario 1
        self.assertFalse(Client().login(username="mesero1", password=PWD))
        self.client.post(self.url())
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.is_active)
        self.assertTrue(Client().login(username="mesero1", password=PWD))
        self.assertTrue(Bitacora.objects.filter(accion="REACTIVATE", entidad_id=self.mesero.pk).exists())

    def test_already_active_user_is_not_logged_twice(self):
        self.client.post(self.url())
        self.client.post(self.url())
        self.assertEqual(Bitacora.objects.filter(accion="REACTIVATE").count(), 1)

    def test_non_admin_forbidden(self):
        c = Client()
        c.force_login(self.admin)
        self.admin.rol = "WAITER"
        self.admin.save()
        self.assertEqual(c.get(self.url()).status_code, 403)
        self.assertEqual(c.post(self.url()).status_code, 403)
        self.mesero.refresh_from_db()
        self.assertFalse(self.mesero.is_active)

    def test_list_shows_reactivate_only_for_inactive(self):
        resp = self.client.get(reverse("usuarios:usuario_list"))
        self.assertContains(resp, 'data-cuadra-confirm="reactivate"', count=1)
        self.assertContains(resp, reverse("usuarios:usuario_reactivate", args=[self.mesero.pk]))
