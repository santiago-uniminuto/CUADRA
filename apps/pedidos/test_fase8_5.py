from django.test import TestCase
from django.urls import reverse
from apps.pedidos.models import Mesa, Pedido
from apps.usuarios.models import Sede, Usuario


class TableServiceLifecycleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Sede.objects.create(nombre='F85 Site', direccion='Address')
        cls.site2 = Sede.objects.create(nombre='F85 Site 2', direccion='Address')
        cls.waiter = Usuario.objects.create_user(username='f85_waiter', password='test-pass', nombre='Waiter', rol='WAITER', sede=cls.site)
        cls.other_waiter = Usuario.objects.create_user(username='f85_other', password='test-pass', nombre='Other', rol='WAITER', sede=cls.site)
        cls.remote = Usuario.objects.create_user(username='f85_remote', password='test-pass', nombre='Remote', rol='WAITER', sede=cls.site2)
        cls.admin = Usuario.objects.create_user(username='f85_admin', password='test-pass', nombre='Admin', rol='ADMIN', sede=cls.site)

    def setUp(self):
        self.client.force_login(self.waiter)
        self.table = Mesa.objects.create(sede=self.site, numero=101)

    def test_discard_empty_preserves_occupied_and_owner_then_release(self):
        self.client.post(reverse('pedidos:open_order', args=[self.table.pk]))
        order = Pedido.objects.get(mesa=self.table)
        self.client.post(reverse('pedidos:discard_empty', args=[order.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.estado, Mesa.Estado.OCCUPIED)
        self.assertEqual(self.table.responsable_actual_id, self.waiter.pk)
        self.assertFalse(Pedido.objects.filter(pk=order.pk).exists())
        response = self.client.get(reverse('pedidos:tables'))
        self.assertContains(response, 'Release table')
        self.assertContains(response, '+ New order')
        self.client.post(reverse('pedidos:release_table', args=[self.table.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.estado, Mesa.Estado.AVAILABLE)
        self.assertIsNone(self.table.responsable_actual_id)

    def test_historical_admin_order_does_not_take_ownership(self):
        Pedido.objects.create(mesa=self.table, mesero=self.admin, estado=Pedido.Estado.CLOSED)
        self.client.post(reverse('pedidos:open_order', args=[self.table.pk]))
        order = Pedido.objects.filter(mesa=self.table, estado=Pedido.Estado.OPEN).get()
        self.client.post(reverse('pedidos:discard_empty', args=[order.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.responsable_actual_id, self.waiter.pk)
        self.assertTrue(Pedido.objects.filter(mesa=self.table, mesero=self.admin, estado=Pedido.Estado.CLOSED).exists())

    def test_other_waiter_cannot_release_owned_table(self):
        self.client.post(reverse('pedidos:open_order', args=[self.table.pk]))
        self.client.force_login(self.other_waiter)
        self.assertEqual(self.client.post(reverse('pedidos:release_table', args=[self.table.pk])).status_code, 403)

    def test_other_site_cannot_release_table(self):
        self.client.force_login(self.remote)
        self.assertEqual(self.client.post(reverse('pedidos:release_table', args=[self.table.pk])).status_code, 404)

    def test_new_table_starts_available_without_owner(self):
        new_table = Mesa.objects.create(sede=self.site, numero=102)
        self.assertEqual(new_table.estado, Mesa.Estado.AVAILABLE)
        self.assertIsNone(new_table.responsable_actual_id)

    def test_legacy_occupied_table_can_be_released_without_rewriting_history(self):
        Pedido.objects.create(mesa=self.table, mesero=self.admin, estado=Pedido.Estado.CLOSED)
        self.table.estado = Mesa.Estado.OCCUPIED
        self.table.save(update_fields=['estado'])
        self.client.post(reverse('pedidos:release_table', args=[self.table.pk]))
        self.table.refresh_from_db()
        self.assertEqual(self.table.estado, Mesa.Estado.AVAILABLE)
        self.assertTrue(Pedido.objects.filter(mesa=self.table, mesero=self.admin).exists())
