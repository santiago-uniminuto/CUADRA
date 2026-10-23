from decimal import Decimal
from django.test import Client, TestCase
from django.urls import reverse
from apps.algoritmos.ordenamiento import heap_sort
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.pagos.models import Pago
from apps.pedidos.models import DetallePedido, Mesa, Pedido
from apps.usuarios.models import Sede, Usuario


class HeapSortTests(TestCase):
    def test_heap_sort_numbers_duplicates_and_no_mutation(self):
        source = [5, -1, 8, 5, 0, 2]
        self.assertEqual(heap_sort(source), [-1, 0, 2, 5, 5, 8])
        self.assertEqual(source, [5, -1, 8, 5, 0, 2])
        self.assertEqual(heap_sort([]), [])
        self.assertEqual(heap_sort([1]), [1])

    def test_heap_sort_ranking_descending(self):
        items = [{'id': 1, 'units': 2}, {'id': 2, 'units': 7}, {'id': 3, 'units': 4}]
        self.assertEqual([x['id'] for x in heap_sort(items, key=lambda x: (-x['units'], x['id']))], [2, 3, 1])


class TopProductsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site_a = Sede.objects.create(nombre='Ranking A', direccion='A')
        cls.site_b = Sede.objects.create(nombre='Ranking B', direccion='B')
        cls.admin = Usuario.objects.create_user(username='rankingadmin', password='pass123456', nombre='Admin', rol='ADMIN', sede=cls.site_a)
        cls.cashier = Usuario.objects.create_user(username='rankingcash', password='pass123456', nombre='Cashier', rol='CASHIER', sede=cls.site_a)
        cls.waiter = Usuario.objects.create_user(username='rankingwait', password='pass123456', nombre='Waiter', rol='WAITER', sede=cls.site_a)
        typ = TipoProducto.objects.create(nombre='Ranking Type')
        supplier = Proveedor.objects.create(nombre='Ranking Supplier', contacto='X')
        cls.a = Producto.objects.create(nombre='Aguila', valor_compra=1, valor_venta=10, tipo_producto=typ, proveedor=supplier)
        cls.b = Producto.objects.create(nombre='Corona', valor_compra=1, valor_venta=20, tipo_producto=typ, proveedor=supplier)
        for site, products, paid in [(cls.site_a, [(cls.a, 3, '10.00'), (cls.b, 1, '20.00')], True),
                                     (cls.site_b, [(cls.b, 9, '20.00')], True),
                                     (cls.site_a, [(cls.b, 20, '20.00')], False)]:
            table = Mesa.objects.create(sede=site, numero=Mesa.objects.filter(sede=site).count() + 1)
            order = Pedido.objects.create(mesa=table, mesero=cls.waiter, estado=Pedido.Estado.CLOSED if paid else Pedido.Estado.OPEN)
            for product, units, price in products:
                DetallePedido.objects.create(pedido=order, producto=product, cantidad=units,
                    valor_venta_unitario=Decimal(price), valor_compra_unitario=Decimal('1.00'))
            if paid:
                Pago.objects.create(pedido=order, cajero=cls.cashier, metodo_pago='CASH', valor=Decimal('100.00'))

    def get(self, user, params=None):
        client = Client()
        client.force_login(user)
        return client.get(reverse('reportes:top_products'), params or {})

    def test_admin_global_ranking_counts_paid_only(self):
        response = self.get(self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([(x['name'], x['units']) for x in response.context['ranking']], [('Corona', 10), ('Aguila', 3)])
        self.assertEqual(response.context['ranking'][0]['revenue'], Decimal('200.00'))

    def test_cashier_is_limited_to_own_site_even_with_site_param(self):
        response = self.get(self.cashier, {'site': self.site_b.pk})
        self.assertEqual([(x['name'], x['units']) for x in response.context['ranking']], [('Aguila', 3), ('Corona', 1)])

    def test_admin_site_filter(self):
        response = self.get(self.admin, {'site': self.site_b.pk})
        self.assertEqual([(x['name'], x['units']) for x in response.context['ranking']], [('Corona', 9)])

    def test_waiter_forbidden(self):
        self.assertEqual(self.get(self.waiter).status_code, 403)

    def test_invalid_date_does_not_show_sales(self):
        response = self.get(self.admin, {'start': '2026-99-99'})
        self.assertTrue(response.context['error'])
        self.assertEqual(response.context['ranking'], [])
