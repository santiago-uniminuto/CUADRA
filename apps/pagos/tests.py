from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.inventario.models import Inventario
from apps.pedidos.models import Mesa, Pedido, DetallePedido
from apps.usuarios.models import Sede, Usuario
from .models import Pago


class CheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Sede.objects.create(nombre='Main', direccion='A')
        cls.other = Sede.objects.create(nombre='Other', direccion='B')
        cls.cashier = Usuario.objects.create_user(username='cashier_s4', password='test-pass', nombre='Cashier', rol='CASHIER', sede=cls.site)
        cls.waiter = Usuario.objects.create_user(username='waiter_s4', password='test-pass', nombre='Waiter', rol='WAITER', sede=cls.site)
        cls.table = Mesa.objects.create(sede=cls.site, numero=1, estado=Mesa.Estado.OCCUPIED)
        cls.other_table = Mesa.objects.create(sede=cls.other, numero=1, estado=Mesa.Estado.OCCUPIED)
        cls.kind = TipoProducto.objects.create(nombre='Type')
        cls.supplier = Proveedor.objects.create(nombre='Supplier', contacto='Contact')
        cls.product = Producto.objects.create(nombre='Item', valor_compra=Decimal('4.00'), valor_venta=Decimal('10.00'), tipo_producto=cls.kind, proveedor=cls.supplier)

    def setUp(self):
        self.client.force_login(self.cashier)
        self.order = Pedido.objects.create(mesa=self.table, mesero=self.waiter)
        DetallePedido.objects.create(pedido=self.order, producto=self.product, cantidad=2, valor_venta_unitario=Decimal('10.00'), valor_compra_unitario=Decimal('4.00'))
        self.stock = Inventario.objects.create(sede=self.site, producto=self.product, cantidad=5)

    def pay(self, order=None, method='CASH'):
        payload = {'method': method}
        if method == 'CASH':
            payload['cash_received'] = '20.00'
        return self.client.post(reverse('pagos:register_payment', args=[(order or self.order).pk]), payload)

    def test_successful_payment_closes_order_and_keeps_table_occupied(self):
        self.assertEqual(self.pay().status_code, 302)
        self.order.refresh_from_db(); self.stock.refresh_from_db(); self.table.refresh_from_db()
        self.assertEqual(self.order.estado, Pedido.Estado.CLOSED)
        self.assertEqual(self.stock.cantidad, 3)
        self.assertEqual(self.table.estado, Mesa.Estado.OCCUPIED)
        self.assertEqual(Pago.objects.get(pedido=self.order).valor, Decimal('20.00'))

    def test_repeated_payment_cannot_deduct_twice(self):
        self.pay(); self.pay(); self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad, 3)
        self.assertEqual(Pago.objects.filter(pedido=self.order).count(), 1)

    def test_insufficient_stock_does_not_charge_or_close(self):
        self.stock.cantidad=1; self.stock.save(update_fields=['cantidad']); self.pay()
        self.order.refresh_from_db(); self.stock.refresh_from_db()
        self.assertEqual(self.order.estado, Pedido.Estado.OPEN)
        self.assertEqual(self.stock.cantidad, 1)
        self.assertFalse(Pago.objects.filter(pedido=self.order).exists())

    def test_invalid_payment_method_is_rejected(self):
        self.pay(method='TRANSFER')
        self.assertFalse(Pago.objects.filter(pedido=self.order).exists())

    def test_waiter_cannot_collect_payment(self):
        self.client.force_login(self.waiter)
        self.assertEqual(self.pay().status_code, 403)
        self.assertFalse(Pago.objects.filter(pedido=self.order).exists())

    def test_other_site_order_is_inaccessible(self):
        other_order = Pedido.objects.create(mesa=self.other_table, mesero=self.waiter)
        self.assertEqual(self.pay(other_order).status_code, 404)

    def test_empty_order_cannot_be_paid(self):
        self.order.detalles.all().delete(); self.pay()
        self.assertFalse(Pago.objects.filter(pedido=self.order).exists())

    def test_paid_table_accepts_new_order(self):
        self.pay()
        self.client.force_login(self.waiter)
        self.assertEqual(self.client.post(reverse('pedidos:open_order', args=[self.table.pk])).status_code, 302)
        self.assertEqual(Pedido.objects.filter(mesa=self.table, estado=Pedido.Estado.OPEN).count(), 1)

    def test_cash_payment_records_received_amount_and_change(self):
        response = self.client.post(reverse('pagos:register_payment', args=[self.order.pk]),
                                    {'method': 'CASH', 'cash_received': '50.00'})
        self.assertEqual(response.status_code, 302)
        payment = Pago.objects.get(pedido=self.order)
        self.assertEqual(payment.efectivo_recibido, Decimal('50.00'))
        self.assertEqual(payment.cambio, Decimal('30.00'))

    def test_insufficient_cash_does_not_charge_or_deduct_stock(self):
        response = self.client.post(reverse('pagos:register_payment', args=[self.order.pk]),
                                    {'method': 'CASH', 'cash_received': '10.00'})
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(self.order.estado, Pedido.Estado.OPEN)
        self.assertEqual(self.stock.cantidad, 5)
        self.assertFalse(Pago.objects.filter(pedido=self.order).exists())

    def test_cash_without_received_amount_is_rejected(self):
        response = self.client.post(reverse('pagos:register_payment', args=[self.order.pk]),
                                    {'method': 'CASH'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Pago.objects.filter(pedido=self.order).exists())

    def test_card_payment_does_not_require_cash_received(self):
        self.assertEqual(self.pay(method='DEBIT').status_code, 302)
        payment = Pago.objects.get(pedido=self.order)
        self.assertIsNone(payment.efectivo_recibido)
        self.assertIsNone(payment.cambio)

    def test_receipt_requires_successful_payment(self):
        response = self.client.get(reverse('pagos:receipt', args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cash_receipt_displays_payment_snapshot_and_change(self):
        self.pay()
        response = self.client.get(reverse('pagos:receipt', args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sales receipt')
        self.assertContains(response, 'Change due')
        self.assertContains(response, 'Cash received')
        self.assertContains(response, 'Internal sales receipt')
        self.assertEqual(Pago.objects.filter(pedido=self.order).count(), 1)

    def test_card_receipt_does_not_show_cash_fields(self):
        self.pay(method='DEBIT')
        response = self.client.get(reverse('pagos:receipt', args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Debit card')
        self.assertNotContains(response, 'Change due')

    def test_waiter_cannot_view_receipt(self):
        self.pay()
        self.client.force_login(self.waiter)
        self.assertEqual(self.client.get(reverse('pagos:receipt', args=[self.order.pk])).status_code, 403)

    def test_other_site_receipt_is_not_accessible(self):
        self.pay()
        other_cashier = Usuario.objects.create_user(
            username='cashier_other_receipt', password='test-pass', nombre='Other cashier',
            rol='CASHIER', sede=self.other)
        self.client.force_login(other_cashier)
        self.assertEqual(self.client.get(reverse('pagos:receipt', args=[self.order.pk])).status_code, 404)
