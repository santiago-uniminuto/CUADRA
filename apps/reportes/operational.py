"""Operational reports: sales are based on registered payments, not open orders."""
from decimal import Decimal
from datetime import datetime, time, timedelta
from io import BytesIO

from django.http import HttpResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.inventario.models import Inventario
from apps.pagos.models import Pago
from apps.usuarios.decorators import get_rol_efectivo, get_sede_efectiva, role_required
from apps.usuarios.models import Sede


def _safe_parse_date(value):
    """Return None for malformed or impossible ISO dates instead of raising."""
    if not value:
        return None
    try:
        return parse_date(value)
    except (TypeError, ValueError):
        return None


def _filters(request):
    start_raw = request.GET.get('start', '').strip()
    end_raw = request.GET.get('end', '').strip()
    start = _safe_parse_date(start_raw)
    end = _safe_parse_date(end_raw)
    if (start_raw and start is None) or (end_raw and end is None) or (start and end and start > end):
        return None, None, 'Enter a valid date range (YYYY-MM-DD).'
    return start, end, None


def _apply_payment_date_filters(payments, start, end):
    """Filter using local-time datetime bounds, avoiding MySQL DATE/TZ table conversion."""
    tz = timezone.get_current_timezone()
    if start:
        start_dt = timezone.make_aware(datetime.combine(start, time.min), tz)
        payments = payments.filter(fecha__gte=start_dt)
    if end:
        end_exclusive = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz)
        payments = payments.filter(fecha__lt=end_exclusive)
    return payments


def _site(request):
    if get_rol_efectivo(request) != 'ADMIN':
        site = get_sede_efectiva(request)
        if site is None:
            raise PermissionDenied('No site assigned.')
        return site, False
    site_id = request.GET.get('site', '').strip()
    if not site_id:
        return None, True
    if not site_id.isdecimal():
        raise PermissionDenied('Invalid site.')
    return Sede.objects.filter(pk=int(site_id)).first() or _missing_site(), True


def _missing_site():
    raise PermissionDenied('Unknown site.')


@role_required('ADMIN', 'CASHIER')
def sales_report(request):
    site, is_admin = _site(request)
    start, end, error = _filters(request)
    payments = Pago.objects.select_related('pedido__mesa__sede', 'cajero').all()
    if site:
        payments = payments.filter(pedido__mesa__sede=site)
    payments = _apply_payment_date_filters(payments, start, end)
    payments = payments.order_by('-fecha', '-pk')
    total = (payments.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')) if not error else Decimal('0.00')
    return render(request, 'reportes/sales.html', {
        'payments': payments if not error else [], 'total': total,
        'count': payments.count() if not error else 0, 'error': error,
        'start': request.GET.get('start', ''), 'end': request.GET.get('end', ''),
        'site': site, 'is_admin_report': is_admin,
        'sites': Sede.objects.order_by('nombre') if is_admin else [],
    })


@role_required('ADMIN', 'CASHIER')
def inventory_report(request):
    site, is_admin = _site(request)
    start, end, error = _filters(request)
    # Stock is a current snapshot; filtering it by historical date would be misleading.
    stock = Inventario.objects.select_related('sede', 'producto').all()
    if site:
        stock = stock.filter(sede=site)
    stock = stock.order_by('sede__nombre', 'producto__nombre', 'pk')
    return render(request, 'reportes/inventory.html', {
        'stock': stock if not error else [], 'error': error,
        'site': site, 'is_admin_report': is_admin,
        'sites': Sede.objects.order_by('nombre') if is_admin else [],
        'start': request.GET.get('start', ''), 'end': request.GET.get('end', ''),
    })


def _xlsx_response(filename, sheet_name, headers, rows, summary=None):
    """Build a small, formatted Excel workbook without writing files to disk."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    if summary:
        for line in summary:
            sheet.append(line)
        sheet.append([])
    sheet.append(headers)
    header_row = sheet.max_row
    for cell in sheet[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="253B52")
    for row in rows:
        sheet.append(list(row))
    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.auto_filter.ref = f"A{header_row}:{sheet.cell(sheet.max_row, len(headers)).coordinate}"
    for column in sheet.columns:
        cells = list(column)
        max_length = max((len(str(cell.value)) if cell.value is not None else 0 for cell in cells), default=0)
        sheet.column_dimensions[cells[0].column_letter].width = min(max(max_length + 2, 12), 36)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@role_required('ADMIN', 'CASHIER')
def sales_export(request):
    site, _is_admin = _site(request)
    start, end, error = _filters(request)
    if error:
        return HttpResponse(error, status=400, content_type="text/plain; charset=utf-8")
    payments = Pago.objects.select_related('pedido__mesa__sede', 'cajero').all()
    if site:
        payments = payments.filter(pedido__mesa__sede=site)
    payments = _apply_payment_date_filters(payments, start, end)
    payments = payments.order_by('-fecha', '-pk')
    rows = ((p.fecha.replace(tzinfo=None), p.pedido.mesa.sede.nombre, p.pedido_id,
             p.cajero.nombre, p.get_metodo_pago_display(), float(p.valor)) for p in payments)
    label = site.nombre if site else 'All sites'
    summary = [["CUADRA — Sales report"], ["Scope", label], ["From", start.isoformat() if start else "Any"],
               ["To", end.isoformat() if end else "Any"], ["Payments", payments.count()],
               ["Total sales", float(payments.aggregate(total=Sum('valor'))['total'] or Decimal('0.00'))]]
    return _xlsx_response('cuadra_sales_report.xlsx', 'Sales',
                           ['Paid at', 'Site', 'Order', 'Cashier', 'Payment method', 'Amount'], rows, summary)


@role_required('ADMIN', 'CASHIER')
def inventory_export(request):
    site, _is_admin = _site(request)
    stock = Inventario.objects.select_related('sede', 'producto').all()
    if site:
        stock = stock.filter(sede=site)
    stock = stock.order_by('sede__nombre', 'producto__nombre', 'pk')
    label = site.nombre if site else 'All sites'
    summary = [["CUADRA — Current inventory snapshot"], ["Scope", label],
               ["Note", "Current stock only; historical inventory is not available."]]
    rows = ((item.sede.nombre, item.producto.nombre, item.cantidad) for item in stock)
    return _xlsx_response('cuadra_inventory_snapshot.xlsx', 'Inventory',
                           ['Site', 'Product', 'Available units'], rows, summary)


@role_required('ADMIN')
def general_report(request):
    """HU030/HU032: consolidated sales and current inventory across sites."""
    site, _is_admin = _site(request)  # HU030-E2: LOCATION (ALL) o una sede
    start, end, error = _filters(request)
    payments = Pago.objects.select_related('pedido__mesa__sede', 'cajero').all()
    stock = Inventario.objects.select_related('sede', 'producto')
    if site:
        payments = payments.filter(pedido__mesa__sede=site)
        stock = stock.filter(sede=site)
    payments = _apply_payment_date_filters(payments, start, end).order_by('-fecha', '-pk')
    stock = stock.order_by('sede__nombre', 'producto__nombre', 'pk')
    if error:
        payments = []
    total = payments.aggregate(total=Sum('valor'))['total'] or Decimal('0.00') if not error else Decimal('0.00')
    return render(request, 'reportes/general.html', {
        'payments': payments, 'stock': stock, 'total': total,
        'count': payments.count() if not error else 0, 'error': error,
        'start': request.GET.get('start', ''), 'end': request.GET.get('end', ''),
        'site_count': Sede.objects.filter(activo=True).count(),
        'site': site, 'sites': Sede.objects.order_by('nombre'),
    })


@role_required('ADMIN')
def general_export(request):
    """HU031: export the consolidated report using the same date filter.

    Administrator only, like general_report (closing audit: this view was
    missing its access control and was reachable without signing in).
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    site, _is_admin = _site(request)  # HU031-E2: conserva el filtro de sede de la pantalla
    start, end, error = _filters(request)
    if error:
        return HttpResponse(error, status=400, content_type='text/plain; charset=utf-8')
    payments = Pago.objects.select_related('pedido__mesa__sede', 'cajero').all()
    stock = Inventario.objects.select_related('sede', 'producto')
    if site:
        payments = payments.filter(pedido__mesa__sede=site)
        stock = stock.filter(sede=site)
    payments = _apply_payment_date_filters(payments, start, end).order_by('-fecha', '-pk')
    stock = stock.order_by('sede__nombre', 'producto__nombre', 'pk')
    scope = site.nombre if site else 'All sites'
    workbook = Workbook()
    sales = workbook.active
    sales.title = 'Sales'
    sales.append(['CUADRA — Consolidated sales report', scope])
    sales.append(['From', start.isoformat() if start else 'Any'])
    sales.append(['To', end.isoformat() if end else 'Any'])
    sales.append(['Payments', payments.count()])
    sales.append(['Total sales', float(payments.aggregate(total=Sum('valor'))['total'] or Decimal('0.00'))])
    sales.append([])
    sales.append(['Paid at', 'Site', 'Order', 'Cashier', 'Payment method', 'Amount'])
    for cell in sales[sales.max_row]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='116B56')
    for item in payments:
        sales.append([item.fecha.replace(tzinfo=None), item.pedido.mesa.sede.nombre,
                      item.pedido_id, item.cajero.nombre, item.get_metodo_pago_display(), float(item.valor)])
    sales.freeze_panes = 'A8'
    sales.auto_filter.ref = f'A7:F{sales.max_row}'
    inventory = workbook.create_sheet('Current inventory')
    inventory.append(['CUADRA — Current inventory snapshot', scope])
    inventory.append(['Note', 'Current stock only; historical inventory is not available.'])
    inventory.append(['Site', 'Product', 'Available units'])
    for cell in inventory[3]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='116B56')
    for item in stock:
        inventory.append([item.sede.nombre, item.producto.nombre, item.cantidad])
    inventory.freeze_panes = 'A4'
    inventory.auto_filter.ref = f'A3:C{inventory.max_row}'
    for sheet in workbook.worksheets:
        for column in sheet.columns:
            cells = list(column)
            longest = max((len(str(cell.value)) if cell.value is not None else 0 for cell in cells), default=0)
            sheet.column_dimensions[cells[0].column_letter].width = min(max(longest + 2, 12), 36)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="cuadra_consolidated_report.xlsx"'
    return response
