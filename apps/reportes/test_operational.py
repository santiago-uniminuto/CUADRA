from decimal import Decimal
from django.test import Client, TestCase
from django.urls import reverse
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.inventario.models import Inventario
from apps.pagos.models import Pago
from apps.pedidos.models import Mesa, Pedido
from apps.usuarios.models import Sede, Usuario


class OperationalReportsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Sede.objects.create(nombre='Zone A', direccion='A')
        cls.b = Sede.objects.create(nombre='Zone B', direccion='B')
        cls.admin = Usuario.objects.create_user(username='admrep', password='pass123456', nombre='Admin', rol='ADMIN', sede=cls.a)
        cls.cashier = Usuario.objects.create_user(username='cashrep', password='pass123456', nombre='Cashier', rol='CASHIER', sede=cls.a)
        cls.other = Usuario.objects.create_user(username='cashother', password='pass123456', nombre='Other', rol='CASHIER', sede=cls.b)
        cls.waiter = Usuario.objects.create_user(username='waitrep', password='pass123456', nombre='Waiter', rol='WAITER', sede=cls.a)
        typ = TipoProducto.objects.create(nombre='Drinks')
        supplier = Proveedor.objects.create(nombre='Provider', contacto='X')
        product = Producto.objects.create(nombre='Water', valor_compra=1, valor_venta=3, tipo_producto=typ, proveedor=supplier)
        Inventario.objects.create(sede=cls.a, producto=product, cantidad=7)
        Inventario.objects.create(sede=cls.b, producto=product, cantidad=12)
        for site, cashier, amount in [(cls.a, cls.cashier, '15.00'), (cls.b, cls.other, '25.00')]:
            table = Mesa.objects.create(numero=1, sede=site)
            order = Pedido.objects.create(mesa=table, mesero=cls.waiter, estado=Pedido.Estado.CLOSED)
            Pago.objects.create(pedido=order, cajero=cashier, metodo_pago='CASH', valor=Decimal(amount))

    def get(self, user, report, data=None):
        client = Client()
        client.force_login(user)
        return client.get(reverse('reportes:' + report), data or {})

    def test_cashier_sales_are_site_scoped(self):
        response = self.get(self.cashier, 'sales', {'site': self.b.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['count'], 1)
        self.assertEqual(response.context['total'], Decimal('15.00'))

    def test_admin_sees_consolidated_and_site_sales(self):
        self.assertEqual(self.get(self.admin, 'sales').context['total'], Decimal('40.00'))
        self.assertEqual(self.get(self.admin, 'sales', {'site': self.b.pk}).context['total'], Decimal('25.00'))

    def test_inventory_site_isolation(self):
        self.assertEqual([r.cantidad for r in self.get(self.cashier, 'inventory').context['stock']], [7])
        self.assertEqual(sorted(r.cantidad for r in self.get(self.admin, 'inventory').context['stock']), [7, 12])

    def test_invalid_date_does_not_return_sales(self):
        response = self.get(self.admin, 'sales', {'start': '2026-99-99'})
        self.assertEqual(response.context['count'], 0)
        self.assertTrue(response.context['error'])

    def test_sales_date_filter_includes_payments_in_selected_local_date_range(self):
        from datetime import datetime
        from django.utils import timezone
        local_tz = timezone.get_current_timezone()
        Pago.objects.all().update(fecha=timezone.make_aware(datetime(2026, 10, 22, 13, 18), local_tz))
        response = self.get(self.admin, 'sales', {'start': '2026-10-01', 'end': '2026-10-31'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['count'], 2)
        self.assertEqual(response.context['total'], Decimal('40.00'))

    def test_waiter_cannot_access_reports(self):
        for report in ('sales', 'inventory'):
            self.assertEqual(self.get(self.waiter, report).status_code, 403)

    def test_admin_acting_as_cashier_only_sees_selected_site(self):
        client = Client()
        client.force_login(self.admin)
        client.post(reverse('usuarios:act_as'), {'rol': 'CASHIER', 'sede': self.b.pk})
        response = client.get(reverse('reportes:sales'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], Decimal('25.00'))
        self.assertFalse(response.context['is_admin_report'])

    def test_cashier_sales_export_is_limited_to_own_site(self):
        from io import BytesIO
        from openpyxl import load_workbook
        response = self.get(self.cashier, 'sales_export', {'site': self.b.pk})
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        sheet = load_workbook(BytesIO(response.content), read_only=True).active
        values = list(sheet.values)
        self.assertTrue(any(len(row) >= 2 and row[0] == 'Scope' and row[1] == 'Zone A' for row in values))
        self.assertTrue(any(len(row) >= 2 and row[0] == 'Payments' and row[1] == 1 for row in values))
        self.assertNotIn(('Zone B',), values)
        self.assertTrue(any(row and row[1] == 'Zone A' for row in values if len(row) > 1))

    def test_admin_inventory_export_can_include_all_sites(self):
        from io import BytesIO
        from openpyxl import load_workbook
        response = self.get(self.admin, 'inventory_export')
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.content), read_only=True).active
        values = list(sheet.values)
        self.assertTrue(any(len(row) >= 2 and row[0] == 'Zone A' for row in values))
        self.assertTrue(any(len(row) >= 2 and row[0] == 'Zone B' for row in values))

    def test_invalid_date_is_rejected_by_sales_export(self):
        response = self.get(self.admin, 'sales_export', {'start': '2026-99-99'})
        self.assertEqual(response.status_code, 400)

    def test_general_report_consolidates_sales_and_inventory_for_admin(self):
        response = self.get(self.admin, 'general')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['count'], 2)
        self.assertEqual(response.context['total'], Decimal('40.00'))
        self.assertEqual(sorted(item.cantidad for item in response.context['stock']), [7, 12])

    def test_general_report_is_not_available_while_admin_acts_as_cashier(self):
        client = Client()
        client.force_login(self.admin)
        client.post(reverse('usuarios:act_as'), {'rol': 'CASHIER', 'sede': self.b.pk})
        self.assertEqual(client.get(reverse('reportes:general')).status_code, 403)

    def test_general_export_contains_sales_and_current_inventory_sheets(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from datetime import datetime
        from django.utils import timezone
        # Pin the payment dates: the fixture creates them "now", which falls outside October after that month.
        Pago.objects.all().update(fecha=timezone.make_aware(datetime(2026, 10, 22, 13, 18), timezone.get_current_timezone()))
        response = self.get(self.admin, 'general_export', {'start': '2026-10-01', 'end': '2026-10-31'})
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content), read_only=True)
        self.assertEqual(workbook.sheetnames, ['Sales', 'Current inventory'])
        sales = list(workbook['Sales'].values)
        inventory = list(workbook['Current inventory'].values)
        self.assertTrue(any(row and row[0] == 'Total sales' and row[1] == 40 for row in sales))
        self.assertTrue(any(len(row) >= 2 and row[0] == 'Zone A' for row in inventory))
        self.assertTrue(any(len(row) >= 2 and row[0] == 'Zone B' for row in inventory))

    def test_invalid_date_is_rejected_by_general_export(self):
        response = self.get(self.admin, 'general_export', {'start': '2026-99-99'})
        self.assertEqual(response.status_code, 400)
