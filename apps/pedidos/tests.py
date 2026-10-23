from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import Sede, Usuario
from .models import Mesa, Pedido


class WaiterOrderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Sede.objects.create(nombre='Test site', direccion='Test address')
        cls.other_site = Sede.objects.create(nombre='Other site', direccion='Other address')
        cls.waiter = Usuario.objects.create_user(username='test_waiter', password='test-pass', nombre='Waiter', rol='WAITER', sede=cls.site)
        cls.cashier = Usuario.objects.create_user(username='test_cashier', password='test-pass', nombre='Cashier', rol='CASHIER', sede=cls.site)
        cls.table = Mesa.objects.create(sede=cls.site, numero=1)
        cls.other_table = Mesa.objects.create(sede=cls.other_site, numero=1)

    def setUp(self):
        self.client.force_login(self.waiter)

    def test_open_order_keeps_table_occupied(self):
        response = self.client.post(reverse('pedidos:open_order', args=[self.table.pk]))
        self.assertEqual(response.status_code, 302)
        self.table.refresh_from_db()
        self.assertEqual(self.table.estado, Mesa.Estado.OCCUPIED)
        self.assertEqual(Pedido.objects.filter(mesa=self.table, estado='OPEN').count(), 1)

    def test_prevent_duplicate_open_order(self):
        url = reverse('pedidos:open_order', args=[self.table.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(Pedido.objects.filter(mesa=self.table, estado='OPEN').count(), 1)

    def test_other_site_cannot_open_order(self):
        response = self.client.post(reverse('pedidos:open_order', args=[self.other_table.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cannot_release_table_with_open_order(self):
        self.client.post(reverse('pedidos:open_order', args=[self.table.pk]))
        self.client.post(reverse('pedidos:release_table', args=[self.table.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.estado, Mesa.Estado.OCCUPIED)

    def test_empty_order_can_be_discarded(self):
        self.client.post(reverse('pedidos:open_order', args=[self.table.pk]))
        order = Pedido.objects.get(mesa=self.table)
        self.client.post(reverse('pedidos:discard_empty', args=[order.pk]))
        self.assertFalse(Pedido.objects.filter(pk=order.pk).exists())

    def test_cashier_cannot_manage_waiter_tables(self):
        self.client.force_login(self.cashier)
        response = self.client.post(reverse('pedidos:open_order', args=[self.table.pk]))
        self.assertEqual(response.status_code, 403)


class TableManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Sede.objects.create(nombre='Management site', direccion='Test')
        cls.other = Sede.objects.create(nombre='Management other', direccion='Test')
        cls.admin = Usuario.objects.create_user(username='table_admin', password='test-pass', nombre='Admin', rol='ADMIN', sede=cls.site)
        cls.waiter = Usuario.objects.create_user(username='table_waiter', password='test-pass', nombre='Waiter', rol='WAITER', sede=cls.site)
        cls.table = Mesa.objects.create(sede=cls.site, numero=1)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_can_create_table_at_selected_site(self):
        self.client.post(reverse('pedidos:create_table'), {'site': self.other.pk, 'number': '12'})
        self.assertTrue(Mesa.objects.filter(sede=self.other, numero=12, activo=True).exists())

    def test_duplicate_number_is_not_created(self):
        self.client.post(reverse('pedidos:create_table'), {'site': self.site.pk, 'number': '1'})
        self.assertEqual(Mesa.objects.filter(sede=self.site, numero=1).count(), 1)

    def test_disabled_table_is_hidden_from_waiter_and_can_be_reenabled(self):
        url = reverse('pedidos:toggle_table', args=[self.table.pk])
        self.client.post(url)
        self.table.refresh_from_db()
        self.assertFalse(self.table.activo)
        self.client.force_login(self.waiter)
        response = self.client.get(reverse('pedidos:tables'))
        self.assertNotIn(self.table, response.context['tables'])
        self.assertEqual(self.client.post(reverse('pedidos:open_order', args=[self.table.pk])).status_code, 404)
        self.client.force_login(self.admin)
        self.client.post(url)
        self.table.refresh_from_db()
        self.assertTrue(self.table.activo)

    def test_table_with_open_order_cannot_be_disabled(self):
        Pedido.objects.create(mesa=self.table, mesero=self.waiter)
        self.client.post(reverse('pedidos:toggle_table', args=[self.table.pk]))
        self.table.refresh_from_db()
        self.assertTrue(self.table.activo)

    def test_occupied_table_cannot_be_disabled_even_without_open_order(self):
        self.table.estado = Mesa.Estado.OCCUPIED
        self.table.save(update_fields=['estado'])
        self.client.post(reverse('pedidos:toggle_table', args=[self.table.pk]))
        self.table.refresh_from_db()
        self.assertTrue(self.table.activo)

    def test_waiter_cannot_manage_tables(self):
        self.client.force_login(self.waiter)
        self.assertEqual(self.client.get(reverse('pedidos:manage_tables')).status_code, 403)
        self.assertEqual(self.client.post(reverse('pedidos:create_table'), {'site': self.site.pk, 'number': 8}).status_code, 403)
        self.assertEqual(self.client.post(reverse('pedidos:toggle_table', args=[self.table.pk])).status_code, 403)

    def test_get_does_not_modify_tables(self):
        self.client.get(reverse('pedidos:manage_tables'))
        self.assertEqual(Mesa.objects.count(), 1)
