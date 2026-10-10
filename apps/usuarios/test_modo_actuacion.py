"""
Modo actuación del admin (requisito de la Propuesta Comercial): el admin puede
actuar como mesero o cajero de UNA sede sin perder su rol real; mientras actúa
solo ve lo de ese rol y esa sede, y las pantallas de Administrador se bloquean
hasta que vuelve ("Return to Admin").
"""
from django.test import Client, TestCase
from django.urls import reverse

from apps.auditoria.models import Bitacora
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.inventario.models import Inventario

from .models import Sede, Usuario

PWD = "Str0ng-Pass#2026"
ADMIN_ONLY_URLS = ["usuarios:usuario_list", "catalogo:producto_list", "usuarios:sede_list"]


class ActuacionBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.zona_t = Sede.objects.create(nombre="Zona T", direccion="x")
        cls.galerias = Sede.objects.create(nombre="Galerias", direccion="y")
        cls.admin = Usuario.objects.create_user(
            username="admin", password=PWD, nombre="Admin", rol=Usuario.Rol.ADMIN, sede=cls.zona_t)
        cls.mesero = Usuario.objects.create_user(
            username="mesero1", password=PWD, nombre="Maria", rol=Usuario.Rol.MESERO, sede=cls.zona_t)
        tipo = TipoProducto.objects.create(nombre="Cervezas")
        prov = Proveedor.objects.create(nombre="Bavaria", contacto="1")
        cls.corona = Producto.objects.create(nombre="Corona", valor_compra=1, valor_venta=2, tipo_producto=tipo, proveedor=prov)
        cls.poker = Producto.objects.create(nombre="Poker", valor_compra=1, valor_venta=2, tipo_producto=tipo, proveedor=prov)
        Inventario.objects.create(producto=cls.corona, sede=cls.zona_t, cantidad=5)
        Inventario.objects.create(producto=cls.poker, sede=cls.galerias, cantidad=7)

    def setUp(self):
        self.client.force_login(self.admin)

    def act_as(self, rol="WAITER", sede=None, **kw):
        return self.client.post(reverse("usuarios:act_as"), {"rol": rol, "sede": (sede or self.galerias).pk}, **kw)


class PureAdminTests(ActuacionBase):
    def test_pure_admin_reaches_every_screen(self):
        for name in ADMIN_ONLY_URLS + ["inventario:inventario_list"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_nav_offers_act_as(self):
        resp = self.client.get(reverse("usuarios:usuario_list"))
        self.assertContains(resp, "Act as Waiter")
        self.assertNotContains(resp, "Return to Admin")


class ActingTests(ActuacionBase):
    def test_acting_as_waiter_sees_only_that_site(self):
        resp = self.act_as("WAITER", self.galerias, follow=True)
        self.assertContains(resp, "Inventory — Galerias")
        self.assertContains(resp, "Poker")
        self.assertNotContains(resp, "Corona")  # lo de Zona T (su sede real) no se mezcla

    def test_real_role_and_site_never_change(self):
        self.act_as("WAITER", self.galerias)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, Usuario.Rol.ADMIN)
        self.assertEqual(self.admin.sede, self.zona_t)

    def test_admin_screens_are_blocked_while_acting(self):
        self.act_as("WAITER", self.galerias)
        for name in ADMIN_ONLY_URLS:  # vistas de clase (mixin) y de función (decorador)
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_cashier_mode_blocks_waiter_and_admin_screens(self):
        self.act_as("CASHIER", self.galerias)
        for name in ADMIN_ONLY_URLS + ["inventario:inventario_list"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_nav_shows_badge_and_return_button(self):
        resp = self.act_as("WAITER", self.galerias, follow=True)
        self.assertContains(resp, "Acting as Waiter")
        self.assertContains(resp, "Return to Admin")
        self.assertNotContains(resp, "Act as Cashier")

    def test_cannot_start_acting_twice(self):
        self.act_as("WAITER", self.galerias)
        self.assertEqual(self.act_as("CASHIER", self.zona_t).status_code, 403)

    def test_invalid_data_does_not_activate(self):
        self.client.post(reverse("usuarios:act_as"), {"rol": "ADMIN", "sede": self.galerias.pk})
        self.client.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": 9999})
        self.assertEqual(self.client.get(reverse("usuarios:usuario_list")).status_code, 200)

    def test_only_post_allowed(self):
        self.assertEqual(self.client.get(reverse("usuarios:act_as")).status_code, 405)
        self.assertEqual(self.client.get(reverse("usuarios:return_to_admin")).status_code, 405)

    def test_actions_are_audited(self):
        self.act_as("WAITER", self.galerias)
        self.client.post(reverse("usuarios:return_to_admin"))
        self.assertTrue(Bitacora.objects.filter(accion="ACT_AS", usuario=self.admin).exists())
        self.assertTrue(Bitacora.objects.filter(accion="RETURN_TO_ADMIN", usuario=self.admin).exists())


class ReturnToAdminTests(ActuacionBase):
    def test_return_restores_admin_screens_and_own_site(self):
        self.act_as("WAITER", self.galerias)
        self.client.post(reverse("usuarios:return_to_admin"))
        for name in ADMIN_ONLY_URLS:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.session["sede_activa_id"], self.zona_t.pk)
        resp = self.client.get(reverse("inventario:inventario_list"))
        self.assertContains(resp, "Inventory — Zona T")  # vuelve a su sede propia


class NonAdminTests(ActuacionBase):
    def setUp(self):
        self.client.force_login(self.mesero)

    def test_waiter_cannot_act_as_anything(self):
        resp = self.client.post(reverse("usuarios:act_as"), {"rol": "CASHIER", "sede": self.galerias.pk})
        self.assertEqual(resp.status_code, 403)

    def test_forged_session_key_gives_a_waiter_nothing(self):
        s = self.client.session
        s["actuando_como"] = "ADMIN"
        s["sede_activa_id"] = self.galerias.pk
        s.save()
        self.assertEqual(self.client.get(reverse("usuarios:usuario_list")).status_code, 403)
        resp = self.client.get(reverse("inventario:inventario_list"))
        self.assertContains(resp, "Inventory — Zona T")  # su sede real, no la de la sesión
