"""Bitácora: eventos de seguridad, cambios, pantalla de consulta y solo lectura."""
import time
from datetime import datetime

from django.contrib import admin
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.usuarios.models import Sede, Usuario

from .models import Bitacora

PWD = "Str0ng-Pass#2026"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sede = Sede.objects.create(nombre="Zona T", direccion="x")
        cls.admin = Usuario.objects.create_user(username="admin", password=PWD, nombre="Laura Admin", rol="ADMIN", sede=cls.sede)
        cls.mesero = Usuario.objects.create_user(username="mesero1", password=PWD, nombre="Maria Rojas", rol="WAITER", sede=cls.sede)

    def entradas(self, accion):
        return Bitacora.objects.filter(accion=accion)

    def entrar(self, username="mesero1", password=PWD, **extra):
        c = Client()
        return c, c.post(reverse("autenticacion:login"), {"username": username, "password": password}, **extra)


class EventosDeSeguridadTests(Base):
    def test_login_is_logged_with_the_ip(self):
        self.entrar()
        e = self.entradas("LOGIN").get()
        self.assertEqual((e.usuario, e.detalle), (self.mesero, "from 127.0.0.1"))

    def test_the_ip_comes_from_what_nginx_writes(self):
        self.entrar(HTTP_X_REAL_IP="10.0.0.7")
        self.assertEqual(self.entradas("LOGIN").get().detalle, "from 10.0.0.7")

    def test_failed_login_of_an_existing_user_is_tied_to_that_user(self):
        self.entrar(password="mala")
        e = self.entradas("LOGIN_FAILED").get()
        self.assertEqual(e.usuario, self.mesero)
        self.assertFalse(self.entradas("LOGIN").exists())

    def test_failed_login_with_unknown_name_does_not_store_what_was_typed(self):
        # La gente a veces teclea su contraseña en el campo de usuario: no debe quedar escrita.
        self.entrar(username="MiClaveSecreta123", password="x")
        e = self.entradas("LOGIN_FAILED").get()
        self.assertIsNone(e.usuario)
        self.assertEqual(e.detalle, "from 127.0.0.1")
        self.assertFalse(Bitacora.objects.filter(detalle__icontains="MiClaveSecreta123").exists())

    def test_inactive_user_login_is_a_failed_attempt(self):
        self.mesero.is_active = False
        self.mesero.save()
        self.entrar()
        self.assertTrue(self.entradas("LOGIN_FAILED").exists())
        self.assertFalse(self.entradas("LOGIN").exists())

    def test_logout_is_logged(self):
        c, _ = self.entrar()
        c.post(reverse("autenticacion:logout"))
        self.assertEqual(self.entradas("LOGOUT").get().usuario, self.mesero)

    def test_inactivity_is_logged_as_its_own_event_not_as_a_logout(self):
        c, _ = self.entrar()
        s = c.session
        s["last_activity"] = time.time() - 4 * 60
        s.save()
        c.get(reverse("autenticacion:home"))
        self.assertEqual(self.entradas("SESSION_EXPIRED").get().usuario, self.mesero)
        self.assertFalse(self.entradas("LOGOUT").exists())

    def test_signing_in_elsewhere_logs_the_closed_session(self):
        self.entrar()
        self.entrar()
        self.assertEqual(self.entradas("SESSION_REPLACED").get().usuario, self.mesero)

    def test_a_single_login_does_not_log_a_replaced_session(self):
        self.entrar()
        self.assertFalse(self.entradas("SESSION_REPLACED").exists())


class CambiosTests(Base):
    def setUp(self):
        self.client.force_login(self.admin)
        Bitacora.objects.all().delete()  # solo interesa lo que hacen las vistas de abajo

    def test_catalog_changes_are_logged(self):
        tipo = TipoProducto.objects.create(nombre="Cervezas")
        prov = Proveedor.objects.create(nombre="Bavaria", contacto="1")
        self.client.post(reverse("catalogo:producto_create"), {"nombre": "Aguila", "valor_compra": "1", "valor_venta": "2", "tipo_producto": tipo.pk, "proveedor": prov.pk})
        producto = Producto.objects.get(nombre="Aguila")
        self.client.post(reverse("catalogo:producto_edit", args=[producto.pk]), {"nombre": "Aguila Light", "valor_compra": "1", "valor_venta": "2", "tipo_producto": tipo.pk, "proveedor": prov.pk})
        self.client.post(reverse("catalogo:proveedor_create"), {"nombre": "Postobon", "contacto": "2"})
        self.client.post(reverse("catalogo:tipoproducto_create"), {"nombre": "Gaseosas"})
        detalles = list(Bitacora.objects.order_by("id").values_list("accion", "entidad", "detalle"))
        self.assertEqual(detalles, [
            ("CREATE", "Producto", "Created product Aguila"),
            ("UPDATE", "Producto", "Updated product Aguila Light"),
            ("CREATE", "Proveedor", "Created supplier Postobon"),
            ("CREATE", "TipoProducto", "Created product type Gaseosas"),
        ])

    def test_site_changes_are_logged(self):
        self.client.post(reverse("usuarios:sede_create"), {"nombre": "Galerias", "direccion": "y"})
        sede = Sede.objects.get(nombre="Galerias")
        self.client.post(reverse("usuarios:sede_edit", args=[sede.pk]), {"nombre": "Galerias Centro", "direccion": "y"})
        self.assertEqual(list(Bitacora.objects.order_by("id").values_list("accion", "detalle")),
                         [("CREATE", "Created site Galerias"), ("UPDATE", "Updated site Galerias Centro")])

    def test_a_rejected_form_logs_nothing(self):
        self.client.post(reverse("catalogo:proveedor_create"), {"nombre": "", "contacto": "2"})
        self.assertFalse(Bitacora.objects.exists())


class DashboardMuestraAlResto(Base):
    def test_dashboard_feed_includes_what_other_users_did(self):
        Client().post(reverse("autenticacion:login"), {"username": "mesero1", "password": PWD})
        self.client.force_login(self.admin)
        html = self.client.get(reverse("reportes:dashboard")).content.decode()
        self.assertIn("Maria Rojas", html)
        self.assertIn("Signed in", html)
        self.assertIn(reverse("auditoria:bitacora_list"), html)


class PantallaTests(Base):
    def setUp(self):
        self.client.force_login(self.admin)
        Bitacora.objects.all().delete()

    def crear(self, n, **kw):
        for i in range(n):
            Bitacora.objects.create(usuario=kw.get("usuario", self.admin), accion=kw.get("accion", "UPDATE"),
                                    entidad="Usuario", detalle=f"{kw.get('prefijo', 'evento')} {i}")

    def get(self, **params):
        return self.client.get(reverse("auditoria:bitacora_list"), params)

    def test_only_admin(self):
        c = Client()
        c.force_login(self.mesero)
        self.assertEqual(c.get(reverse("auditoria:bitacora_list")).status_code, 403)
        self.assertEqual(Client().get(reverse("auditoria:bitacora_list")).status_code, 302)
        self.client.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": self.sede.pk})
        self.assertEqual(self.get().status_code, 403)

    def test_newest_first(self):
        self.crear(3)
        html = self.get().content.decode()
        self.assertLess(html.index("evento 2"), html.index("evento 0"))

    def test_filter_by_user(self):
        self.crear(2, usuario=self.admin, prefijo="del admin")
        self.crear(2, usuario=self.mesero, prefijo="del mesero")
        html = self.get(usuario=self.mesero.pk).content.decode()
        self.assertIn("del mesero", html)
        self.assertNotIn("del admin", html)

    def test_filter_by_type_and_action(self):
        self.crear(1, accion="LOGIN_FAILED", prefijo="intento")
        self.crear(1, accion="LOGIN", prefijo="entro")
        self.crear(1, accion="CREATE", prefijo="creo")
        seguridad = self.get(categoria="security").content.decode()
        self.assertIn("intento", seguridad)
        self.assertNotIn("entro", seguridad)
        self.assertNotIn("creo", seguridad)
        cambios = self.get(categoria="change").content.decode()
        self.assertIn("creo", cambios)
        self.assertNotIn("intento", cambios)
        self.assertNotIn("entro", cambios)
        self.assertIn("entro", self.get(accion="LOGIN").content.decode())
        self.assertNotIn("creo", self.get(accion="LOGIN").content.decode())

    def test_filter_by_dates_inclusive(self):
        self.crear(3)
        fechas = [datetime(2026, 10, 1, 8), datetime(2026, 10, 2, 23, 30), datetime(2026, 10, 4, 9)]
        for e, f in zip(Bitacora.objects.order_by("id"), fechas):
            Bitacora.objects.filter(pk=e.pk).update(fecha=timezone.make_aware(f))
        html = self.get(desde="2026-10-02", hasta="2026-10-02").content.decode()
        self.assertIn("evento 1", html)  # 23:30 del último día, aún dentro
        self.assertNotIn("evento 0", html)
        self.assertNotIn("evento 2", html)

    def test_text_search(self):
        self.crear(1, prefijo="Aguila")
        self.crear(1, prefijo="Corona")
        html = self.get(q="aguila").content.decode()
        self.assertIn("Aguila 0", html)
        self.assertNotIn("Corona 0", html)

    def test_invalid_filters_are_ignored(self):
        self.crear(2)
        resp = self.get(usuario="abc", categoria="zzz", accion="NOPE", desde="31-31-31", hasta="x", page="999")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "evento 1")

    def test_pagination_keeps_the_filters(self):
        self.crear(30, prefijo="paginado")
        resp = self.get(q="paginado")
        self.assertEqual(len(resp.context["pagina"].object_list), 25)
        self.assertContains(resp, "q=paginado&amp;page=2")
        self.assertEqual(len(self.get(q="paginado", page=2).context["pagina"].object_list), 5)

    def test_labels_and_empty_state(self):
        self.assertContains(self.get(), "No events match")
        self.crear(1, accion="SESSION_EXPIRED")
        self.assertContains(self.get(), "Session expired (inactivity)")


class SoloLecturaTests(Base):
    def test_the_log_cannot_be_edited_or_deleted_even_from_the_technical_panel(self):
        ma = admin.site._registry[Bitacora]
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        self.client.force_login(self.admin)
        e = Bitacora.objects.create(usuario=self.admin, accion="UPDATE", entidad="Usuario", detalle="x")
        request = type("R", (), {"user": self.admin})()
        self.assertFalse(ma.has_add_permission(request))
        self.assertFalse(ma.has_change_permission(request, e))
        self.assertFalse(ma.has_delete_permission(request, e))
        self.assertEqual(self.client.get(f"/django-admin/auditoria/bitacora/{e.pk}/delete/").status_code, 403)
        self.assertEqual(self.client.get("/django-admin/auditoria/bitacora/add/").status_code, 403)

    def test_known_and_unknown_actions_have_a_label_and_a_category(self):
        self.assertEqual(Bitacora(accion="LOGIN_FAILED").accion_legible, "Failed sign-in")
        self.assertEqual(Bitacora(accion="LOGIN_FAILED").categoria, "security")
        self.assertEqual(Bitacora(accion="ALGO_NUEVO").accion_legible, "ALGO_NUEVO")
        self.assertEqual(Bitacora(accion="ALGO_NUEVO").categoria, "change")


class EventosSinUsuarioTests(Base):
    """Regresión: un intento fallido con un nombre que no existe no tiene usuario, y las pantallas no pueden romperse."""

    def setUp(self):
        Client().post(reverse("autenticacion:login"), {"username": "no-existe", "password": "x"})
        self.assertTrue(Bitacora.objects.filter(accion="LOGIN_FAILED", usuario__isnull=True).exists())
        self.client.force_login(self.admin)

    def test_dashboard_still_renders(self):
        resp = self.client.get(reverse("reportes:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Unknown user")
        self.assertContains(resp, "Failed sign-in")

    def test_activity_log_still_renders_and_names_the_unknown_user(self):
        resp = self.client.get(reverse("auditoria:bitacora_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "<td>Unknown user</td>")

    def test_the_label_of_who_did_it(self):
        self.assertEqual(Bitacora(usuario=self.mesero).quien, "Maria Rojas")
        self.assertEqual(Bitacora(usuario=None).quien, "Unknown user")
        self.mesero.nombre = ""
        self.assertEqual(Bitacora(usuario=self.mesero).quien, "mesero1")
