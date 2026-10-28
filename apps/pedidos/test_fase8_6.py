"""CUADRA phase 8.6 regression tests. Copy to apps/pedidos/test_fase8_6.py."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.inventario.models import Inventario
from apps.pagos.models import Pago
from apps.pedidos.models import DetallePedido, Mesa, Pedido
from apps.usuarios.models import Sede, Usuario


class ReservationFixture:
    def build(self):
        self.site = Sede.objects.create(nombre='Reservation site', direccion='Address')
        self.other_site = Sede.objects.create(nombre='Reservation other site', direccion='Address')
        self.waiters = [
            Usuario.objects.create_user(username=f'reserve_waiter_{i}', password='test-pass',
                                        nombre=f'Waiter {i}', rol='WAITER', sede=self.site)
            for i in (1, 2)
        ]
        self.cashier = Usuario.objects.create_user(username='reserve_cashier', password='test-pass',
                                                   nombre='Cashier', rol='CASHIER', sede=self.site)
        kind = TipoProducto.objects.create(nombre='Reservation type')
        supplier = Proveedor.objects.create(nombre='Reservation supplier', contacto='Contact')
        self.product = Producto.objects.create(nombre='Reserved item', valor_compra=Decimal('4.00'),
                                               valor_venta=Decimal('10.00'), tipo_producto=kind,
                                               proveedor=supplier)
        self.stock = Inventario.objects.create(sede=self.site, producto=self.product, cantidad=1)
        self.tables = [Mesa.objects.create(sede=self.site, numero=i, estado=Mesa.Estado.OCCUPIED,
                                           responsable_actual=self.waiters[i - 1]) for i in (1, 2)]
        self.orders = [Pedido.objects.create(mesa=table, mesero=waiter)
                       for table, waiter in zip(self.tables, self.waiters)]

    def add(self, index, qty=1):
        self.client.force_login(self.waiters[index])
        return self.client.post(reverse('pedidos:add_product', args=[self.orders[index].pk]),
                                {'product': str(self.product.pk), 'quantity': str(qty)})

    def quantity(self, index):
        return (DetallePedido.objects.filter(pedido=self.orders[index], producto=self.product)
                .values_list('cantidad', flat=True).first() or 0)


class ReservationTests(ReservationFixture, TestCase):
    def setUp(self):
        self.build()

    def test_first_registered_order_wins_last_unit(self):
        self.assertEqual(self.add(0).status_code, 302)
        self.assertEqual(self.add(1).status_code, 302)
        self.assertEqual((self.quantity(0), self.quantity(1)), (1, 0))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad, 1)

    def test_same_order_cannot_add_beyond_remaining_units(self):
        self.add(0)
        self.add(0)
        self.assertEqual(self.quantity(0), 1)

    def test_removing_detail_releases_reservation(self):
        self.add(0)
        detail = DetallePedido.objects.get(pedido=self.orders[0], producto=self.product)
        self.client.post(reverse('pedidos:remove_product', args=[self.orders[0].pk, detail.pk]))
        self.add(1)
        self.assertEqual((self.quantity(0), self.quantity(1)), (0, 1))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad, 1)

    def test_reservations_are_separate_per_site(self):
        other_waiter = Usuario.objects.create_user(username='reserve_other_waiter', password='test-pass',
                                                   nombre='Other', rol='WAITER', sede=self.other_site)
        other_table = Mesa.objects.create(sede=self.other_site, numero=1, estado=Mesa.Estado.OCCUPIED,
                                          responsable_actual=other_waiter)
        other_order = Pedido.objects.create(mesa=other_table, mesero=other_waiter)
        Inventario.objects.create(sede=self.other_site, producto=self.product, cantidad=1)
        self.add(0)
        self.client.force_login(other_waiter)
        self.client.post(reverse('pedidos:add_product', args=[other_order.pk]),
                         {'product': self.product.pk, 'quantity': 1})
        self.assertEqual(DetallePedido.objects.get(pedido=other_order).cantidad, 1)

    def test_payment_deducts_once_and_does_not_release_other_reservations(self):
        self.stock.cantidad = 2
        self.stock.save(update_fields=['cantidad'])
        self.add(0)
        self.add(1)
        self.client.force_login(self.cashier)
        url = reverse('pagos:register_payment', args=[self.orders[0].pk])
        self.client.post(url, {'method': 'DEBIT'})
        self.client.post(url, {'method': 'DEBIT'})
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad, 1)
        self.assertEqual(Pago.objects.filter(pedido=self.orders[0]).count(), 1)
        self.assertEqual(self.quantity(1), 1)
        self.client.post(reverse('pagos:register_payment', args=[self.orders[1].pk]),
                         {'method': 'DEBIT'})
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad, 0)
        self.assertEqual(Pago.objects.filter(pedido=self.orders[1]).count(), 1)


class ConcurrentReservationTests(ReservationFixture, TransactionTestCase):
    """Real independent DB connections; only supported on MySQL for this project."""
    def setUp(self):
        self.build()

    def test_two_waiters_race_for_last_unit(self):
        if connection.vendor != 'mysql':
            self.skipTest('Concurrency regression is intended for MySQL/InnoDB.')
        barrier = Barrier(2, timeout=10)

        def attempt(index):
            close_old_connections()
            try:
                client = Client()
                client.force_login(self.waiters[index])
                barrier.wait()
                response = client.post(reverse('pedidos:add_product', args=[self.orders[index].pk]),
                                       {'product': str(self.product.pk), 'quantity': '1'})
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(attempt, i) for i in range(2)]
            codes = [future.result(timeout=25) for future in futures]
        self.assertEqual(codes, [302, 302])
        quantities = [self.quantity(i) for i in range(2)]
        self.assertEqual(sum(quantities), 1, f'Over-reservation: {quantities}')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad, 1)
