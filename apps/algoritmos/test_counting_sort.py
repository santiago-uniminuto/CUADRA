"""Counting Sort integration and receipt permissions regression tests."""
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from apps.algoritmos.ordenamiento import counting_sort
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.inventario.models import Inventario
from apps.pagos.models import Pago
from apps.pedidos.models import Mesa, Pedido, DetallePedido
from apps.usuarios.models import Sede, Usuario


class CountingSortTests(TestCase):
    def test_empty_duplicates_and_stability(self):
        self.assertEqual(counting_sort([]), [])
        rows = [(3, 'a'), (0, 'b'), (3, 'c'), (1, 'd')]
        self.assertEqual(counting_sort(rows, key=lambda x: x[0]),
                         [(0, 'b'), (1, 'd'), (3, 'a'), (3, 'c')])
        self.assertEqual(rows[0], (3, 'a'))

    def test_sparse_large_quantities_and_invalid_keys(self):
        self.assertEqual(counting_sort([1000000, 0, 8]), [0, 8, 1000000])
        with self.assertRaises(ValueError):
            counting_sort([-1, 2])
        with self.assertRaises(ValueError):
            counting_sort([1.5, 2])


class InventoryCountingSortIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Sede.objects.create(nombre='Count Site', direccion='X')
        cls.admin = Usuario.objects.create_user(username='countadmin', password='test-pass', nombre='Admin', rol='ADMIN', sede=cls.site)
        cls.waiter = Usuario.objects.create_user(username='countwaiter', password='test-pass', nombre='Waiter', rol='WAITER', sede=cls.site)
        typ = TipoProducto.objects.create(nombre='Count Type')
        supplier = Proveedor.objects.create(nombre='Count Supplier', contacto='X')
        for name, quantity in [('Zulu', 5), ('Alpha', 5), ('Beta', 0), ('Omega', 1000000)]:
            product = Producto.objects.create(nombre=name, tipo_producto=typ, proveedor=supplier, valor_compra=1, valor_venta=2)
            Inventario.objects.create(sede=cls.site, producto=product, cantidad=quantity)

    def test_quantity_sort_and_default_name_sort(self):
        self.client.force_login(self.admin)
        url = reverse('inventario:stock_list')
        result = self.client.get(url, {'sede': self.site.pk, 'sort': 'quantity'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual([(x['producto'].nombre, x['actual']) for x in result.context['filas']],
                         [('Beta', 0), ('Alpha', 5), ('Zulu', 5), ('Omega', 1000000)])
        result = self.client.get(url, {'sede': self.site.pk})
        self.assertEqual([x['producto'].nombre for x in result.context['filas']],
                         ['Alpha', 'Beta', 'Omega', 'Zulu'])

    def test_waiter_cannot_use_admin_inventory(self):
        self.client.force_login(self.waiter)
        self.assertEqual(self.client.get(reverse('inventario:stock_list'), {'sort': 'quantity'}).status_code, 403)


class ReceiptAdminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Sede.objects.create(nombre='Receipt A', direccion='A')
        cls.b = Sede.objects.create(nombre='Receipt B', direccion='B')
        cls.admin = Usuario.objects.create_user(username='receipt_admin', password='test-pass', nombre='Admin', rol='ADMIN', sede=cls.a)
        cls.cashier = Usuario.objects.create_user(username='receipt_cashier', password='test-pass', nombre='Cashier', rol='CASHIER', sede=cls.a)
        cls.waiter = Usuario.objects.create_user(username='receipt_waiter', password='test-pass', nombre='Waiter', rol='WAITER', sede=cls.a)
        typ = TipoProducto.objects.create(nombre='Receipt Type')
        supplier = Proveedor.objects.create(nombre='Receipt Supplier', contacto='X')
        product = Producto.objects.create(nombre='Receipt Item', tipo_producto=typ, proveedor=supplier, valor_compra=1, valor_venta=10)
        for site in (cls.a, cls.b):
            table = Mesa.objects.create(sede=site, numero=1)
            order = Pedido.objects.create(mesa=table, mesero=cls.waiter, estado=Pedido.Estado.CLOSED)
            DetallePedido.objects.create(pedido=order, producto=product, cantidad=1, valor_venta_unitario=Decimal('10.00'), valor_compra_unitario=Decimal('1.00'))
            Pago.objects.create(pedido=order, cajero=cls.cashier, metodo_pago='DEBIT', valor=Decimal('10.00'))
            if site == cls.a: cls.order_a = order
            else: cls.order_b = order

    def test_admin_can_open_receipts_from_any_site(self):
        self.client.force_login(self.admin)
        for order in (self.order_a, self.order_b):
            response = self.client.get(reverse('pagos:receipt', args=[order.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Sales receipt')

    def test_cashier_only_own_site(self):
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get(reverse('pagos:receipt', args=[self.order_a.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('pagos:receipt', args=[self.order_b.pk])).status_code, 404)

    def test_waiter_forbidden(self):
        self.client.force_login(self.waiter)
        self.assertEqual(self.client.get(reverse('pagos:receipt', args=[self.order_a.pk])).status_code, 403)

    def test_admin_acting_as_cashier_is_scoped(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session['actuando_como'] = 'CASHIER'
        session['sede_activa_id'] = self.a.pk
        session.save()
        self.assertEqual(self.client.get(reverse('pagos:receipt', args=[self.order_a.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('pagos:receipt', args=[self.order_b.pk])).status_code, 404)
