"""Fase 8.7: stock receiving permissions and site isolation."""
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.inventario.models import Inventario
from apps.usuarios.models import Sede, Usuario


class CashierStockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Sede.objects.create(nombre='Stock Site A', direccion='A')
        cls.other = Sede.objects.create(nombre='Stock Site B', direccion='B')
        cls.cashier = Usuario.objects.create_user(username='stock_cashier', password='test-pass', nombre='Cashier', rol='CASHIER', sede=cls.site)
        cls.waiter = Usuario.objects.create_user(username='stock_waiter', password='test-pass', nombre='Waiter', rol='WAITER', sede=cls.site)
        cls.admin = Usuario.objects.create_user(username='stock_admin', password='test-pass', nombre='Admin', rol='ADMIN', sede=cls.site)
        kind = TipoProducto.objects.create(nombre='Stock test kind')
        supplier = Proveedor.objects.create(nombre='Stock test supplier', contacto='Contact')
        cls.product = Producto.objects.create(nombre='Stock item', valor_compra=Decimal('4.00'), valor_venta=Decimal('10.00'), tipo_producto=kind, proveedor=supplier)

    def setUp(self):
        self.client.force_login(self.cashier)

    def test_cashier_can_receive_at_own_site(self):
        response = self.client.post(reverse('inventario:stock_receive'), {'sede': self.site.pk, f'qty_{self.product.pk}': '3'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Inventario.objects.get(sede=self.site, producto=self.product).cantidad, 3)

    def test_cashier_cannot_forge_other_site(self):
        response = self.client.post(reverse('inventario:stock_receive'), {'sede': self.other.pk, f'qty_{self.product.pk}': '7'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Inventario.objects.filter(sede=self.other, producto=self.product).exists())
        self.assertFalse(Inventario.objects.filter(sede=self.site, producto=self.product).exists())

    def test_cashier_get_ignores_other_site_query(self):
        response = self.client.get(reverse('inventario:stock_receive'), {'sede': self.other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['sede'].pk, self.site.pk)
        self.assertNotContains(response, f'<option value="{self.other.pk}"')

    def test_cashier_stock_list_is_scoped(self):
        response = self.client.get(reverse('inventario:stock_list'), {'sede': self.other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['sede'].pk, self.site.pk)
        self.assertNotContains(response, 'Adjust stock')

    def test_cashier_cannot_adjust(self):
        self.assertEqual(self.client.get(reverse('inventario:stock_adjust')).status_code, 403)

    def test_waiter_cannot_receive(self):
        self.client.force_login(self.waiter)
        self.assertEqual(self.client.get(reverse('inventario:stock_receive')).status_code, 403)

    def test_admin_can_receive_at_other_site(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('inventario:stock_receive'), {'sede': self.other.pk, f'qty_{self.product.pk}': '5'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Inventario.objects.get(sede=self.other, producto=self.product).cantidad, 5)

    def test_acting_cashier_cannot_receive_at_other_site(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session['actuando_como'] = 'CASHIER'
        session['sede_activa_id'] = self.other.pk
        session.save()
        response = self.client.post(reverse('inventario:stock_receive'), {'sede': self.site.pk, f'qty_{self.product.pk}': '9'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Inventario.objects.filter(producto=self.product).exists())
        response = self.client.post(reverse('inventario:stock_receive'), {'sede': self.other.pk, f'qty_{self.product.pk}': '2'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Inventario.objects.get(sede=self.other, producto=self.product).cantidad, 2)
