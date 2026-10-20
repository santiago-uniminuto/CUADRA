"""HU044 — Ajustar existencias (corregir el conteo, con motivo obligatorio y bitácora)."""
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Bitacora

from .models import Inventario
from .test_entradas import Base


class AjusteBase(Base):
    def setUp(self):
        super().setUp()
        Inventario.objects.create(producto=self.aguila, sede=self.zona_t, cantidad=5)
        Inventario.objects.create(producto=self.aguila, sede=self.galerias, cantidad=7)

    def ajustar(self, nuevos, visto=None, motivo="Physical count", sede=None, **kw):
        datos = {"sede": (sede or self.zona_t).pk, "motivo": motivo}
        for producto, valor in nuevos.items():
            datos[f"new_{producto.pk}"] = valor
            datos[f"seen_{producto.pk}"] = (visto or {}).get(producto, self.stock(producto, sede) or 0)
        return self.client.post(reverse("inventario:stock_adjust"), datos, **kw)

    def sin_cambios(self):
        self.assertEqual(self.stock(self.aguila), 5)
        self.assertFalse(Bitacora.objects.filter(accion="STOCK_ADJUST").exists())


class AccesoTests(AjusteBase):
    def test_only_admin(self):
        self.assertEqual(self.client.get(reverse("inventario:stock_adjust")).status_code, 200)
        for user in (self.mesero, self.cajero):
            c = Client()
            c.force_login(user)
            self.assertEqual(c.get(reverse("inventario:stock_adjust")).status_code, 403)
            self.assertEqual(c.post(reverse("inventario:stock_adjust"), {"sede": self.zona_t.pk, "motivo": "x y z"}).status_code, 403)
        self.assertEqual(Client().get(reverse("inventario:stock_adjust")).status_code, 302)

    def test_blocked_while_acting(self):
        self.client.post(reverse("usuarios:act_as"), {"rol": "WAITER", "sede": self.zona_t.pk})
        self.assertEqual(self.client.get(reverse("inventario:stock_adjust")).status_code, 403)

    def test_stock_list_links_to_it(self):
        self.assertContains(self.client.get(reverse("inventario:stock_list")), reverse("inventario:stock_adjust"))


class AplicarTests(AjusteBase):
    def test_sets_the_real_value_and_logs_before_after_and_reason(self):
        resp = self.ajustar({self.aguila: "30"}, motivo="Typing mistake", follow=True)
        self.assertEqual(self.stock(self.aguila), 30)
        self.assertContains(resp, "Stock adjusted at Zona T")
        detalle = Bitacora.objects.get(accion="STOCK_ADJUST").detalle
        self.assertEqual(detalle, "Aguila 5 -> 30 at Zona T. Reason: Typing mistake")

    def test_can_lower_to_zero(self):
        self.ajustar({self.aguila: "0"}, motivo="Broken bottles")
        self.assertEqual(self.stock(self.aguila), 0)

    def test_other_sites_are_untouched(self):
        self.ajustar({self.aguila: "30"})
        self.assertEqual(self.stock(self.aguila, self.galerias), 7)

    def test_creates_the_row_for_a_product_never_received(self):
        self.ajustar({self.corona: "12"})
        self.assertEqual(self.stock(self.corona), 12)

    def test_several_products_and_unchanged_lines_are_ignored(self):
        self.ajustar({self.aguila: "9", self.corona: "0"}, visto={self.aguila: 5, self.corona: 0})
        self.assertEqual(self.stock(self.aguila), 9)
        self.assertEqual(Bitacora.objects.filter(accion="STOCK_ADJUST").count(), 1)  # corona 0 -> 0 no es cambio


class ValidacionTests(AjusteBase):
    def test_reason_is_required_and_limited(self):
        for motivo in ("", "  ", "ab"):
            self.assertContains(self.ajustar({self.aguila: "9"}, motivo=motivo), "reason for the adjustment")
        self.assertContains(self.ajustar({self.aguila: "9"}, motivo="x" * 121), "at most 120")
        self.sin_cambios()

    def test_rejects_bad_numbers(self):
        for malo in ("-1", "2.5", "abc", "²", "1000001"):
            self.assertContains(self.ajustar({self.aguila: malo}), "whole number of units")
        self.sin_cambios()

    def test_needs_at_least_one_change(self):
        self.assertContains(self.ajustar({self.aguila: "5"}), "Change the stock of at least one product")  # igual a lo visto
        self.assertContains(self.ajustar({self.aguila: ""}), "Change the stock of at least one product")
        self.sin_cambios()

    def test_all_or_nothing(self):
        self.ajustar({self.aguila: "30", self.corona: "abc"})
        self.sin_cambios()

    def test_missing_seen_value_is_rejected(self):
        self.client.post(reverse("inventario:stock_adjust"), {"sede": self.zona_t.pk, "motivo": "Physical count", f"new_{self.aguila.pk}": "30"})
        self.sin_cambios()

    def test_inactive_products_and_bad_sites(self):
        self.assertNotContains(self.client.get(reverse("inventario:stock_adjust")), "Descontinuado")
        self.galerias.activo = False
        self.galerias.save()
        for sede in ("9999", "abc", "²", str(self.galerias.pk)):
            resp = self.client.post(reverse("inventario:stock_adjust"), {"sede": sede, "motivo": "Physical count"})
            self.assertEqual(resp.status_code, 302, sede)
        self.sin_cambios()


class ConcurrenciaTests(AjusteBase):
    def test_a_sale_in_between_is_not_overwritten(self):
        # El admin ve 5, mientras edita el stock baja a 3 (por ejemplo, un cierre de venta)...
        Inventario.objects.filter(producto=self.aguila, sede=self.zona_t).update(cantidad=3)
        resp = self.ajustar({self.aguila: "30", self.corona: "10"}, visto={self.aguila: 5, self.corona: 0})
        # ...y entonces no se aplica NADA (ni la otra línea) y se avisa.
        self.assertContains(resp, "changed while you were editing (now 3)")
        self.assertEqual(self.stock(self.aguila), 3)
        self.assertIsNone(self.stock(self.corona))
        self.assertFalse(Bitacora.objects.filter(accion="STOCK_ADJUST").exists())

    def test_the_page_comes_back_with_the_new_stock_and_what_was_typed(self):
        Inventario.objects.filter(producto=self.aguila, sede=self.zona_t).update(cantidad=3)
        html = self.ajustar({self.aguila: "30"}, visto={self.aguila: 5}).content.decode()
        self.assertIn(f'name="seen_{self.aguila.pk}" value="3"', html)  # ahora ve lo real
        self.assertIn('value="30"', html)  # y conserva lo escrito
        # reenviando con lo nuevo sí se aplica
        self.ajustar({self.aguila: "30"}, visto={self.aguila: 3})
        self.assertEqual(self.stock(self.aguila), 30)
