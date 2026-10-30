"""
Pruebas de las historias de usuario ajustadas en el cierre del proyecto:
HU024 (editar línea, no borrar el último producto), HU025 (guardar pedido),
HU027-E2 (mensaje sin método de pago) y HU030/HU031 (filtro por sede del consolidado).
"""
from decimal import Decimal
from io import BytesIO

from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.auditoria.models import Bitacora
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.inventario.models import Inventario
from apps.pagos.models import Pago
from apps.pedidos.models import DetallePedido, Mesa, Pedido
from apps.usuarios.models import Sede, Usuario

PWD = "Pass-2026-x"


class Fixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Sede.objects.create(nombre="Zona T", direccion="Bogota")
        cls.other_site = Sede.objects.create(nombre="Galerias", direccion="Bogota")
        cls.waiter = Usuario.objects.create_user("w1", password=PWD, nombre="W1", rol="WAITER", sede=cls.site)
        cls.waiter2 = Usuario.objects.create_user("w2", password=PWD, nombre="W2", rol="WAITER", sede=cls.site)
        cls.cashier = Usuario.objects.create_user("c1", password=PWD, nombre="C1", rol="CASHIER", sede=cls.site)
        cls.admin = Usuario.objects.create_user("a1", password=PWD, nombre="A1", rol="ADMIN", sede=cls.site)
        kind = TipoProducto.objects.create(nombre="Beer")
        supplier = Proveedor.objects.create(nombre="Supplier", contacto="n/a")
        cls.beer = Producto.objects.create(nombre="Beer", valor_compra=Decimal("3000"), valor_venta=Decimal("8000"),
                                           tipo_producto=kind, proveedor=supplier)
        cls.soda = Producto.objects.create(nombre="Soda", valor_compra=Decimal("1000"), valor_venta=Decimal("4000"),
                                           tipo_producto=kind, proveedor=supplier)
        cls.inv_beer = Inventario.objects.create(producto=cls.beer, sede=cls.site, cantidad=10)
        cls.inv_soda = Inventario.objects.create(producto=cls.soda, sede=cls.site, cantidad=5)

    def setUp(self):
        self.table = Mesa.objects.create(sede=self.site, numero=1, estado=Mesa.Estado.OCCUPIED,
                                         responsable_actual=self.waiter)
        self.order = Pedido.objects.create(mesa=self.table, mesero=self.waiter)
        self.client.force_login(self.waiter)

    def line(self, product, qty, order=None):
        return DetallePedido.objects.create(pedido=order or self.order, producto=product, cantidad=qty,
                                            valor_venta_unitario=product.valor_venta,
                                            valor_compra_unitario=product.valor_compra)

    def edit(self, detail, product, qty):
        return self.client.post(reverse("pedidos:edit_item", args=[self.order.pk, detail.pk]),
                                {"product": product.pk, "quantity": qty}, follow=True)


class EditItemTests(Fixture):
    def test_edit_quantity_of_a_line(self):
        d = self.line(self.beer, 2)
        self.assertContains(self.edit(d, self.beer, 4), "Order item updated.")
        d.refresh_from_db()
        self.assertEqual(d.cantidad, 4)
        self.assertTrue(Bitacora.objects.filter(accion="ORDER_EDIT", entidad_id=self.order.pk).exists())

    def test_edit_cannot_exceed_unreserved_stock(self):
        d = self.line(self.beer, 2)
        other_table = Mesa.objects.create(sede=self.site, numero=2, estado=Mesa.Estado.OCCUPIED, responsable_actual=self.waiter2)
        self.line(self.beer, 7, order=Pedido.objects.create(mesa=other_table, mesero=self.waiter2))
        # 10 in stock, 7 reserved by the other table -> this line can grow to 3 but not 4.
        self.assertContains(self.edit(d, self.beer, 4), "Only 3 unit(s) of Beer are free")
        self.edit(d, self.beer, 3)
        d.refresh_from_db()
        self.assertEqual(d.cantidad, 3)

    def test_change_product_of_a_line_freezes_new_price(self):
        d = self.line(self.beer, 2)
        self.edit(d, self.soda, 1)
        d.refresh_from_db()
        self.assertEqual((d.producto_id, d.cantidad, d.valor_venta_unitario), (self.soda.pk, 1, Decimal("4000")))

    def test_change_to_a_product_already_in_order_merges_lines(self):
        d = self.line(self.beer, 2)
        self.line(self.soda, 1)
        self.edit(d, self.soda, 2)
        self.assertEqual(list(self.order.detalles.values_list("producto_id", "cantidad")), [(self.soda.pk, 3)])

    def test_other_waiter_cannot_edit(self):
        d = self.line(self.beer, 2)
        self.client.force_login(self.waiter2)
        self.assertEqual(self.client.post(reverse("pedidos:edit_item", args=[self.order.pk, d.pk]),
                                          {"product": self.beer.pk, "quantity": 1}).status_code, 403)

    def test_closed_order_cannot_be_edited(self):
        d = self.line(self.beer, 2)
        Pedido.objects.filter(pk=self.order.pk).update(estado=Pedido.Estado.CLOSED)
        self.assertEqual(self.client.post(reverse("pedidos:edit_item", args=[self.order.pk, d.pk]),
                                          {"product": self.beer.pk, "quantity": 1}).status_code, 404)


class LastItemTests(Fixture):
    def test_last_product_cannot_be_deleted(self):
        d = self.line(self.beer, 1)
        r = self.client.post(reverse("pedidos:remove_product", args=[self.order.pk, d.pk]), follow=True)
        self.assertContains(r, "An order must have at least one product")
        self.assertTrue(DetallePedido.objects.filter(pk=d.pk).exists())

    def test_one_of_several_products_can_be_deleted(self):
        d = self.line(self.beer, 1)
        self.line(self.soda, 1)
        self.client.post(reverse("pedidos:remove_product", args=[self.order.pk, d.pk]))
        self.assertEqual(list(self.order.detalles.values_list("producto_id", flat=True)), [self.soda.pk])


class SaveOrderTests(Fixture):
    def test_empty_order_cannot_be_saved(self):
        r = self.client.post(reverse("pedidos:save_order", args=[self.order.pk]), follow=True)
        self.assertContains(r, "You must add at least one product")

    def test_saved_order_is_visible_to_cashier_of_same_site(self):
        self.line(self.beer, 1)
        r = self.client.post(reverse("pedidos:save_order", args=[self.order.pk]))
        self.assertRedirects(r, reverse("pedidos:tables"))
        self.assertTrue(Bitacora.objects.filter(accion="ORDER_SAVE", entidad_id=self.order.pk).exists())
        self.client.force_login(self.cashier)
        self.assertIn(self.order, list(self.client.get(reverse("pagos:queue")).context["orders"]))

    def test_cashier_queue_hides_orders_without_products(self):
        self.client.force_login(self.cashier)
        self.assertNotIn(self.order, list(self.client.get(reverse("pagos:queue")).context["orders"]))


class PaymentMethodMessageTests(Fixture):
    def test_missing_method_shows_story_message(self):
        self.line(self.beer, 1)
        self.client.force_login(self.cashier)
        r = self.client.post(reverse("pagos:register_payment", args=[self.order.pk]), {"method": ""}, follow=True)
        self.assertContains(r, "You must select a payment method")
        self.assertFalse(Pago.objects.filter(pedido=self.order).exists())


class ConsolidatedSiteFilterTests(Fixture):
    def setUp(self):
        super().setUp()
        self.line(self.beer, 1)
        Pago.objects.create(pedido=self.order, cajero=self.cashier, metodo_pago="CASH", valor=Decimal("8000"))
        other_table = Mesa.objects.create(sede=self.other_site, numero=1)
        other_order = Pedido.objects.create(mesa=other_table, mesero=self.waiter, estado=Pedido.Estado.CLOSED)
        self.line(self.soda, 1, order=other_order)
        Pago.objects.create(pedido=other_order, cajero=self.cashier, metodo_pago="DEBIT", valor=Decimal("4000"))
        Inventario.objects.create(producto=self.beer, sede=self.other_site, cantidad=3)
        self.client.force_login(self.admin)

    def test_all_sites_by_default(self):
        r = self.client.get(reverse("reportes:general"))
        self.assertEqual((r.context["count"], r.context["total"]), (2, Decimal("12000")))

    def test_single_site_filter(self):
        r = self.client.get(reverse("reportes:general"), {"site": self.other_site.pk})
        self.assertEqual((r.context["count"], r.context["total"]), (1, Decimal("4000")))
        self.assertEqual({i.sede_id for i in r.context["stock"]}, {self.other_site.pk})

    def test_export_keeps_site_filter(self):
        r = self.client.get(reverse("reportes:general_export"), {"site": self.other_site.pk})
        wb = load_workbook(BytesIO(r.content), read_only=True)
        sales = list(wb["Sales"].values)
        self.assertEqual(sales[0][1], "Galerias")
        self.assertTrue(any(row and row[0] == "Total sales" and row[1] == 4000 for row in sales))
        self.assertTrue(all(row[0] == "Galerias" for row in list(wb["Current inventory"].values)[3:]))


class ReservedStockVisibilityTests(Fixture):
    """Las unidades en pedidos abiertos de otra mesa no se muestran como disponibles."""

    def setUp(self):
        super().setUp()
        other_table = Mesa.objects.create(sede=self.site, numero=2, estado=Mesa.Estado.OCCUPIED, responsable_actual=self.waiter2)
        self.other_order = Pedido.objects.create(mesa=other_table, mesero=self.waiter2)
        self.line(self.soda, 5, order=self.other_order)  # the 5 sodas are all taken by table 2

    def test_inventory_shows_available_and_reserved_units(self):
        r = self.client.get(reverse("inventario:inventario_list"))
        soda = next(i for i in r.context["items"] if i.producto_id == self.soda.pk)
        self.assertEqual((soda.cantidad, soda.reservado, soda.disponible), (5, 5, 0))
        self.assertContains(r, "ALL IN OPEN ORDERS")
        self.assertContains(r, "5 of 5 units in open orders")

    def test_order_form_only_offers_products_with_free_units(self):
        r = self.client.get(reverse("pedidos:order_detail", args=[self.order.pk]))
        self.assertEqual([p.pk for p in r.context["products"]], [self.beer.pk])

    def test_clear_message_when_last_units_are_reserved(self):
        r = self.client.post(reverse("pedidos:add_product", args=[self.order.pk]), {"product": self.soda.pk, "quantity": 1}, follow=True)
        self.assertContains(r, "All 5 unit(s) of Soda are already in other open orders")

    def test_cancelling_the_other_order_frees_the_units(self):
        self.client.force_login(self.waiter2)
        r = self.client.post(reverse("pedidos:cancel_order", args=[self.other_order.pk]), follow=True)
        self.assertContains(r, "Order cancelled")
        self.client.force_login(self.waiter)
        soda = next(i for i in self.client.get(reverse("inventario:inventario_list")).context["items"] if i.producto_id == self.soda.pk)
        self.assertEqual(soda.disponible, 5)


class CancelOrderTests(Fixture):
    def test_waiter_cancels_unpaid_order_and_then_releases_table(self):
        self.line(self.beer, 2)
        self.client.post(reverse("pedidos:cancel_order", args=[self.order.pk]))
        self.assertFalse(Pedido.objects.filter(pk=self.order.pk).exists())
        log = Bitacora.objects.get(accion="ORDER_CANCEL", entidad_id=self.order.pk)
        self.assertIn("2 x Beer", log.detalle)
        self.table.refresh_from_db()
        self.assertEqual(self.table.estado, Mesa.Estado.OCCUPIED)  # released explicitly afterwards
        self.client.post(reverse("pedidos:release_table", args=[self.table.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.estado, Mesa.Estado.AVAILABLE)
        self.inv_beer.refresh_from_db()
        self.assertEqual(self.inv_beer.cantidad, 10)  # physical stock untouched

    def test_other_waiter_cannot_cancel(self):
        self.line(self.beer, 1)
        self.client.force_login(self.waiter2)
        self.assertEqual(self.client.post(reverse("pedidos:cancel_order", args=[self.order.pk])).status_code, 403)

    def test_paid_order_cannot_be_cancelled(self):
        self.line(self.beer, 1)
        Pedido.objects.filter(pk=self.order.pk).update(estado=Pedido.Estado.CLOSED)
        self.assertEqual(self.client.post(reverse("pedidos:cancel_order", args=[self.order.pk])).status_code, 404)

    def test_cashier_cannot_cancel(self):
        self.line(self.beer, 1)
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.post(reverse("pedidos:cancel_order", args=[self.order.pk])).status_code, 403)


class EditPanelTests(Fixture):
    def test_edit_opens_in_side_panel(self):
        d = self.line(self.beer, 2)
        r = self.client.get(reverse("pedidos:order_detail", args=[self.order.pk]), {"edit": d.pk})
        self.assertEqual(r.context["edit_detail"], d)
        self.assertContains(r, "Edit item")
        self.assertNotContains(r, "Add product")

    def test_add_panel_by_default(self):
        self.line(self.beer, 2)
        r = self.client.get(reverse("pedidos:order_detail", args=[self.order.pk]))
        self.assertIsNone(r.context["edit_detail"])
        self.assertContains(r, "Add product")
