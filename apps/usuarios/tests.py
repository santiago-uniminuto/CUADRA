from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse

from apps.auditoria.models import Bitacora

from .models import Sede, Usuario

PWD = "Str0ng-Pass#2026"


class BaseUsuariosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.zona_t = Sede.objects.create(nombre="Zona T", direccion="x")
        cls.galerias = Sede.objects.create(nombre="Galerias", direccion="y")
        cls.admin = Usuario.objects.create_user(
            username="admin", password=PWD, nombre="Admin", rol=Usuario.Rol.ADMIN, sede=cls.zona_t)
        cls.mesero = Usuario.objects.create_user(
            username="mesero1", password=PWD, nombre="Maria Lopez", rol=Usuario.Rol.MESERO, sede=cls.zona_t)

    def setUp(self):
        self.client.force_login(self.admin)

    def payload(self, **over):
        data = {"nombre": "Nuevo Cajero", "username": "cajero1", "password1": PWD, "password2": PWD,
                "rol": "CASHIER", "sede": self.galerias.pk}
        data.update(over)
        return data


class AccessTests(BaseUsuariosTest):
    def test_non_admin_forbidden(self):
        c = Client()
        c.force_login(self.mesero)
        for name, args in [("usuario_list", []), ("usuario_create", []), ("usuario_update", [self.admin.pk]),
                           ("usuario_deactivate", [self.admin.pk]), ("usuario_reset_password", [self.admin.pk])]:
            self.assertEqual(c.get(reverse(f"usuarios:{name}", args=args)).status_code, 403, name)
        self.assertEqual(c.post(reverse("usuarios:usuario_assign")).status_code, 403)

    def test_anonymous_redirected_to_login(self):
        resp = Client().get(reverse("usuarios:usuario_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])


class CreateTests(BaseUsuariosTest):  # HU004
    def test_create_ok(self):
        resp = self.client.post(reverse("usuarios:usuario_create"), self.payload())
        self.assertRedirects(resp, reverse("usuarios:usuario_list"))
        u = Usuario.objects.get(username="cajero1")
        self.assertEqual((u.rol, u.sede, u.is_active), ("CASHIER", self.galerias, True))
        self.assertNotEqual(u.password, PWD)
        self.assertTrue(u.check_password(PWD))
        self.assertTrue(Bitacora.objects.filter(accion="CREATE", entidad_id=u.pk).exists())

    def test_duplicate_username(self):
        resp = self.client.post(reverse("usuarios:usuario_create"), self.payload(username="mesero1"))
        self.assertContains(resp, "This username already exists")
        self.assertEqual(Usuario.objects.count(), 2)

    def test_duplicate_username_case_insensitive(self):
        resp = self.client.post(reverse("usuarios:usuario_create"), self.payload(username="MESERO1"))
        self.assertContains(resp, "This username already exists")

    def test_passwords_mismatch(self):
        resp = self.client.post(reverse("usuarios:usuario_create"), self.payload(password2="otra"))
        self.assertContains(resp, "Passwords do not match")
        self.assertFalse(Usuario.objects.filter(username="cajero1").exists())

    def test_required_fields(self):
        resp = self.client.post(reverse("usuarios:usuario_create"), {})
        self.assertContains(resp, "This field is required.")
        self.assertEqual(Usuario.objects.count(), 2)

    def test_weak_password_rejected(self):
        resp = self.client.post(reverse("usuarios:usuario_create"),
                               self.payload(password1="123", password2="123"))
        self.assertFalse(Usuario.objects.filter(username="cajero1").exists())
        self.assertEqual(resp.status_code, 200)

    def test_single_role_stored(self):
        self.client.post(reverse("usuarios:usuario_create"), self.payload(rol="WAITER"))
        self.assertEqual(Usuario.objects.get(username="cajero1").rol, "WAITER")

    def test_invalid_role_rejected(self):
        self.client.post(reverse("usuarios:usuario_create"), self.payload(rol="SUPERBOSS"))
        self.assertFalse(Usuario.objects.filter(username="cajero1").exists())


class UpdateTests(BaseUsuariosTest):  # HU005
    def test_loads_current_data(self):
        resp = self.client.get(reverse("usuarios:usuario_update", args=[self.mesero.pk]))
        self.assertContains(resp, "Maria Lopez")

    def test_update_ok(self):
        resp = self.client.post(reverse("usuarios:usuario_update", args=[self.mesero.pk]),
                                {"nombre": "Maria L.", "rol": "CASHIER", "sede": self.galerias.pk})
        self.assertRedirects(resp, reverse("usuarios:usuario_list"))
        self.mesero.refresh_from_db()
        self.assertEqual((self.mesero.nombre, self.mesero.rol, self.mesero.sede), ("Maria L.", "CASHIER", self.galerias))

    def test_empty_name_rejected(self):
        resp = self.client.post(reverse("usuarios:usuario_update", args=[self.mesero.pk]),
                                {"nombre": "  ", "rol": "WAITER", "sede": self.zona_t.pk})
        self.assertContains(resp, "Name is required.")
        self.mesero.refresh_from_db()
        self.assertEqual(self.mesero.nombre, "Maria Lopez")

    def test_admin_cannot_demote_self(self):
        resp = self.client.post(reverse("usuarios:usuario_update", args=[self.admin.pk]),
                                {"nombre": "Admin", "rol": "WAITER", "sede": self.zona_t.pk})
        self.assertContains(resp, "cannot remove your own Administrator role")
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, "ADMIN")


class DeactivateTests(BaseUsuariosTest):  # HU006
    def test_get_asks_confirmation_and_changes_nothing(self):
        resp = self.client.get(reverse("usuarios:usuario_deactivate", args=[self.mesero.pk]))
        self.assertContains(resp, "Are you sure")
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.is_active)

    def test_confirm_deactivates_and_blocks_login(self):
        self.client.post(reverse("usuarios:usuario_deactivate", args=[self.mesero.pk]))
        self.mesero.refresh_from_db()
        self.assertFalse(self.mesero.is_active)
        self.assertFalse(Client().login(username="mesero1", password=PWD))
        self.assertTrue(Bitacora.objects.filter(accion="DEACTIVATE", entidad_id=self.mesero.pk).exists())

    def test_open_session_is_closed(self):
        other = Client()
        other.force_login(self.mesero)
        self.assertEqual(other.get(reverse("inventario:inventario_list")).status_code, 200)
        self.client.post(reverse("usuarios:usuario_deactivate", args=[self.mesero.pk]))
        resp = other.get(reverse("inventario:inventario_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_cannot_deactivate_self(self):
        self.client.post(reverse("usuarios:usuario_deactivate", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class AssignTests(BaseUsuariosTest):  # HU007
    def test_assign_ok_replaces_role(self):
        resp = self.client.post(reverse("usuarios:usuario_assign"),
                                {"usuario": self.mesero.pk, "rol": "CASHIER", "sede": self.galerias.pk})
        self.assertRedirects(resp, reverse("usuarios:usuario_list"))
        self.mesero.refresh_from_db()
        self.assertEqual((self.mesero.rol, self.mesero.sede), ("CASHIER", self.galerias))
        self.assertEqual(self.mesero.nombre, "Maria Lopez")  # el resto de datos no cambia

    def test_incomplete_fields(self):
        resp = self.client.post(reverse("usuarios:usuario_assign"),
                                {"usuario": self.mesero.pk, "rol": "", "sede": ""}, follow=True)
        self.assertContains(resp, "User, role and site are required.")
        self.mesero.refresh_from_db()
        self.assertEqual(self.mesero.rol, "WAITER")

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse("usuarios:usuario_assign")).status_code, 405)

    def test_admin_cannot_demote_self(self):
        self.client.post(reverse("usuarios:usuario_assign"),
                         {"usuario": self.admin.pk, "rol": "WAITER", "sede": self.zona_t.pk})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, "ADMIN")


class ResetPasswordTests(BaseUsuariosTest):  # HU008
    def test_reset_ok(self):
        new = "Another-Pass#77"
        resp = self.client.post(reverse("usuarios:usuario_reset_password", args=[self.mesero.pk]),
                                {"password1": new, "password2": new})
        self.assertRedirects(resp, reverse("usuarios:usuario_list"))
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.check_password(new))

    def test_mismatch(self):
        resp = self.client.post(reverse("usuarios:usuario_reset_password", args=[self.mesero.pk]),
                                {"password1": "Another-Pass#77", "password2": "x"})
        self.assertContains(resp, "Passwords do not match")
        self.mesero.refresh_from_db()
        self.assertTrue(self.mesero.check_password(PWD))


class ListTests(BaseUsuariosTest):  # HU009
    def test_lists_all_with_columns(self):
        resp = self.client.get(reverse("usuarios:usuario_list"))
        self.assertContains(resp, "Maria Lopez")
        self.assertContains(resp, "Waiter")
        self.assertContains(resp, "Zona T")
        self.assertContains(resp, "Active")

    def test_search_by_name(self):
        resp = self.client.get(reverse("usuarios:usuario_list"), {"q": "maria"})
        self.assertContains(resp, "Maria Lopez")
        self.assertEqual(len(resp.context["usuarios"]), 1)

    def test_search_no_results(self):
        resp = self.client.get(reverse("usuarios:usuario_list"), {"q": "zzzz"})
        self.assertContains(resp, "No results found")

    def test_inactive_shown(self):
        self.mesero.is_active = False
        self.mesero.save()
        self.assertContains(self.client.get(reverse("usuarios:usuario_list")), "Inactive")
