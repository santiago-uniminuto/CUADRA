"""Sumatoria y algoritmo voraz del vuelto: resultados correctos y uso real en caja."""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.inventario.models import Inventario
from apps.pedidos.models import DetallePedido, Mesa, Pedido
from apps.usuarios.models import Sede, Usuario

from .calculos import DENOMINACIONES_COP, desglose_vuelto, sumatoria


class SumatoriaTests(SimpleTestCase):
    def test_matches_builtin_sum(self):
        for datos in ([], [5], [1, 2, 3, 4], [-3, 3, 10]):
            self.assertEqual(sumatoria(datos), sum(datos))

    def test_accepts_generators_and_keeps_decimal_type(self):
        total = sumatoria((Decimal('1.10') * n for n in (1, 2)), Decimal('0.00'))
        self.assertEqual(total, Decimal('3.30'))
        self.assertIsInstance(total, Decimal)
        self.assertEqual(sumatoria([], Decimal('0.00')), Decimal('0.00'))


class DesgloseVueltoTests(SimpleTestCase):
    def test_greedy_picks_largest_denominations_first(self):
        desglose, resto = desglose_vuelto(Decimal('187550'))
        self.assertEqual(desglose, [
            (Decimal('100000'), 1), (Decimal('50000'), 1), (Decimal('20000'), 1),
            (Decimal('10000'), 1), (Decimal('5000'), 1), (Decimal('2000'), 1),
            (Decimal('500'), 1), (Decimal('50'), 1),
        ])
        self.assertEqual(resto, Decimal('0'))

    def test_breakdown_always_adds_up_to_the_change(self):
        for cambio in (0, 50, 1950, 3000, 99950, 250000, 1234550):
            desglose, resto = desglose_vuelto(Decimal(cambio))
            entregado = sum(d * c for d, c in desglose)
            self.assertEqual(entregado + resto, Decimal(cambio))
            self.assertEqual(resto, Decimal('0'))

    def test_amount_not_multiple_of_the_smallest_coin_leaves_a_remainder(self):
        desglose, resto = desglose_vuelto(Decimal('99999'))
        self.assertEqual(sum(d * c for d, c in desglose) + resto, Decimal('99999'))
        self.assertEqual(resto, Decimal('49'))

    def test_amount_below_smallest_coin_is_left_as_remainder(self):
        desglose, resto = desglose_vuelto(Decimal('30.00'))
        self.assertEqual(desglose, [])
        self.assertEqual(resto, Decimal('30.00'))
        desglose, resto = desglose_vuelto(Decimal('1000.75'))
        self.assertEqual(desglose, [(Decimal('1000'), 1)])
        self.assertEqual(resto, Decimal('0.75'))

    def test_zero_change_needs_nothing(self):
        self.assertEqual(desglose_vuelto(Decimal('0.00')), ([], Decimal('0.00')))

    def test_negative_change_is_rejected(self):
        with self.assertRaises(ValueError):
            desglose_vuelto(Decimal('-1'))

    def test_denominations_in_any_order_give_the_same_result(self):
        revuelto = tuple(reversed(DENOMINACIONES_COP))
        self.assertEqual(desglose_vuelto(Decimal('73250'), revuelto),
                         desglose_vuelto(Decimal('73250')))


class VueltoEnCajaTests(TestCase):
    """El cajero ve qué billetes y monedas devolver una vez registrado el pago."""

    @classmethod
    def setUpTestData(cls):
        cls.site = Sede.objects.create(nombre='Main', direccion='A')
        cls.cashier = Usuario.objects.create_user(username='cajero_vuelto', password='test-pass',
                                                  nombre='Cashier', rol='CASHIER', sede=cls.site)
        cls.waiter = Usuario.objects.create_user(username='mesero_vuelto', password='test-pass',
                                                 nombre='Waiter', rol='WAITER', sede=cls.site)
        cls.table = Mesa.objects.create(sede=cls.site, numero=1, estado=Mesa.Estado.OCCUPIED)
        tipo = TipoProducto.objects.create(nombre='Type')
        proveedor = Proveedor.objects.create(nombre='Supplier', contacto='Contact')
        cls.product = Producto.objects.create(nombre='Item', valor_compra=Decimal('4000.00'),
                                              valor_venta=Decimal('12500.00'),
                                              tipo_producto=tipo, proveedor=proveedor)

    def setUp(self):
        self.client.force_login(self.cashier)
        self.order = Pedido.objects.create(mesa=self.table, mesero=self.waiter)
        DetallePedido.objects.create(pedido=self.order, producto=self.product, cantidad=2,
                                     valor_venta_unitario=Decimal('12500.00'),
                                     valor_compra_unitario=Decimal('4000.00'))
        Inventario.objects.create(sede=self.site, producto=self.product, cantidad=5)

    def pay(self, method, cash=None):
        payload = {'method': method}
        if cash is not None:
            payload['cash_received'] = cash
        self.client.post(reverse('pagos:register_payment', args=[self.order.pk]), payload)
        return self.client.get(reverse('pagos:checkout_detail', args=[self.order.pk]))

    def test_cash_payment_shows_bills_and_coins_to_hand_back(self):
        # total 25.000, recibe 100.000 -> vuelto 75.000 = 50.000 + 20.000 + 5.000
        response = self.pay('CASH', '100000.00')
        self.assertContains(response, 'Give back')
        self.assertContains(response, '1 × $50.000,00')
        self.assertContains(response, '1 × $20.000,00')
        self.assertContains(response, '1 × $5.000,00')

    def test_exact_cash_shows_no_breakdown(self):
        response = self.pay('CASH', '25000.00')
        self.assertNotContains(response, 'Give back')

    def test_card_payment_shows_no_breakdown(self):
        response = self.pay('DEBIT')
        self.assertNotContains(response, 'Give back')
