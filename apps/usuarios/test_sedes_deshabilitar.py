"""Deshabilitar / reactivar sedes y sus efectos en usuarios y en el modo actuación."""
from django.test import Client, TestCase
from django.urls import reverse

from apps.auditoria.models import Bitacora

from .forms import AsignarRolSedeForm, UsuarioCreateForm, UsuarioUpdateForm
from .models import Sede, Usuario

PWD = "Str0ng-Pass#2026"


class SedeToggleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.zona_t = Sede.objects.create(nombre="Zona T", direccion="x")
        cls.galerias = Sede.objects.create(nombre="Galerias", direccion="y")
        cls.admin = Usuario.objects.create_user(username="admin", password=PWD, nombre="Admin", rol="ADMIN", sede=cls.zona_t)
        cls.mesero = Usuario.objects.create_user(username="mesero1", password=PWD, nombre="Maria", rol="WAITER", sede=cls.galerias)

    def setUp(self):
        self.client.force_login(self.admin)

    def url(self, sede=None):
        return reverse("usuarios:sede_toggle", args=[(sede or self.galerias).pk])

    def test_cannot_deactivate_a_site_with_active_users(self):
        resp = self.client.post(self.url(), follow=True)
        self.assertContains(resp, "still has active users")
        self.galerias.refresh_from_db()
        self.assertTrue(self.galerias.activo)

    def test_can_deactivate_once_its_users_are_inactive(self):
        self.mesero.is_active = False
        self.mesero.save()
        self.assertContains(self.client.get(self.url()), "Are you sure you want to deactivate")
        self.client.post(self.url())
        self.galerias.refresh_from_db()
        self.assertFalse(self.galerias.activo)
        self.assertTrue(Bitacora.objects.filter(accion="DEACTIVATE", entidad="Sede", entidad_id=self.galerias.pk).exists())

    def test_inactive_site_is_not_offered_anywhere(self):
        self.mesero.is_active = False
        self.mesero.save()
        self.client.post(self.url())
        self.assertNotIn(self.galerias, UsuarioCreateForm().fields["sede"].queryset)
        self.assertNotIn(self.galerias, AsignarRolSedeForm().fields["sede"].queryset)
        self.assertNotContains(self.client.get(reverse("usuarios:usuario_list")), 'value="%d"' % self.galerias.pk + ">Galerias")
        # ni en el selector "Act as" de la barra, ni aceptada por la vista
        resp = self.client.get(reverse("usuarios:sede_list"))
        self.assertNotContains(resp, '<option value="%d">Galerias' % self.galerias.pk)
        self.client.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": self.galerias.pk})
        self.assertEqual(self.client.get(reverse("usuarios:usuario_list")).status_code, 200)  # no quedó actuando

    def test_user_keeps_current_site_in_edit_form_even_if_inactive(self):
        self.mesero.is_active = False
        self.mesero.save()
        self.client.post(self.url())
        form = UsuarioUpdateForm(instance=self.mesero)
        self.assertIn(self.galerias, form.fields["sede"].queryset)

    def test_cannot_reactivate_a_user_whose_site_is_inactive(self):
        self.mesero.is_active = False
        self.mesero.save()
        self.client.post(self.url())
        resp = self.client.post(reverse("usuarios:usuario_reactivate", args=[self.mesero.pk]), follow=True)
        self.assertContains(resp, "is inactive")
        self.mesero.refresh_from_db()
        self.assertFalse(self.mesero.is_active)
        # al reactivar la sede, ya se puede
        self.client.post(self.url())
        self.client.post(reverse("usuarios:usuario_reactivate", args=[self.mesero.pk]))
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.is_active)

    def test_list_shows_status_and_buttons(self):
        resp = self.client.get(reverse("usuarios:sede_list"))
        self.assertContains(resp, "DEACTIVATE")
        self.assertNotContains(resp, 'data-cuadra-confirm="reactivate"')

    def test_non_admin_forbidden(self):
        waiter = Client()
        waiter.force_login(self.mesero)
        self.assertEqual(waiter.post(self.url()).status_code, 403)
