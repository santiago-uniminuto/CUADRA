import re

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.algoritmos.ordenamiento import counting_sort, insertion_sort, merge_sort
from apps.auditoria.utils import registrar
from apps.catalogo.models import Producto
from apps.pedidos.models import Pedido
from apps.pedidos.reservas import reservas_por_producto
from apps.usuarios.decorators import get_sede_efectiva, get_rol_efectivo, role_required
from apps.usuarios.models import Sede

from .models import Inventario

MAX_ENTRADA = 100_000  # tope por línea: evita errores de digitación (300000 en vez de 30)
MAX_EXISTENCIA = 1_000_000
MAX_MOTIVO = 120


@role_required("WAITER")
def inventario_list(request):
    """
    HU019 — Consultar inventario por sede (Escenarios 1-3): el mesero solo ve
    los productos de SU sede, con búsqueda por nombre.
    HU021 — Bloqueo de productos sin stock (Escenarios 1-2): se marcan los
    productos con cantidad 0 como "OUT OF STOCK". El botón "Add" queda
    deshabilitado para esos; agregarlos al pedido de verdad se implementa en
    HU023 (Sprint 4), esta pantalla solo deja preparado el bloqueo visual.

    El orden final se calcula con ordenamiento por inserción (requisito
    de algoritmos funcionales del proyecto), por cantidad disponible: primero lo que hay
    menos stock (a igual cantidad, por nombre), útil para que el mesero note
    rápido qué se está agotando.
    """
    query = request.GET.get("q", "").strip()
    sede = get_sede_efectiva(request)  # la propia, o la elegida si el admin actúa como mesero
    items_qs = Inventario.objects.select_related("producto__tipo_producto").filter(sede=sede, producto__activo=True)
    if query:
        items_qs = items_qs.filter(producto__nombre__icontains=query)
    # Disponible = existencia física menos lo que ya está en pedidos abiertos (aún sin pagar)
    # de la sede. Así un mesero no ve "3 en stock" si otra mesa ya pidió esas 3 unidades.
    reservado = reservas_por_producto(sede)
    items = list(items_qs)
    for i in items:
        i.reservado = reservado.get(i.producto_id, 0)
        i.disponible = max(i.cantidad - i.reservado, 0)
    items = insertion_sort(items, key=lambda i: (i.disponible, i.producto.nombre.lower()))
    # El selector de Inventory solo ofrece pedidos del mesero actual.
    # El endpoint pedidos:add_product valida tambien la propiedad del pedido
    # en el servidor (parche Control de Mesas por Mesero).
    open_orders = list(Pedido.objects.filter(
        mesa__sede=sede, estado=Pedido.Estado.OPEN, mesero=request.user,
    ).select_related('mesa').order_by('mesa__numero', 'pk'))
    return render(request, "inventario/inventario_list.html", {
        "items": items, "query": query, "sede": sede, "open_orders": open_orders,
    })


# ---------------------------------------------------------------- Administrador: existencias y entradas
def _entero(valor):
    """Entero a partir de texto, o None. Solo dígitos ASCII (str.isdigit() acepta caracteres como '²' y luego int() falla)."""
    return int(valor) if valor is not None and re.fullmatch(r"[0-9]{1,9}", str(valor)) else None


def _sede_elegida(request, valor):
    """La sede pedida en la URL o el formulario (solo activas); si no hay, la del propio administrador."""
    activas = Sede.objects.filter(activo=True)
    pk = _entero(valor)
    if pk is not None:
        elegida = activas.filter(pk=pk).first()
        if elegida:
            return elegida
    return activas.filter(pk=request.user.sede_id).first() or activas.order_by("nombre").first()


def _filas_de_stock(sede, query=""):
    """Todos los productos ACTIVOS con su existencia en la sede (0 si nunca se ha recibido), por nombre."""
    productos = Producto.objects.select_related("tipo_producto").filter(activo=True)
    if query:
        productos = productos.filter(nombre__icontains=query)
    existencias = dict(Inventario.objects.filter(sede=sede).values_list("producto_id", "cantidad"))
    filas = [{"producto": p, "actual": existencias.get(p.pk, 0)} for p in productos]
    return merge_sort(filas, key=lambda f: f["producto"].nombre.lower())


@role_required("ADMIN", "CASHIER")
def stock_list(request):
    """
    Existencias de CUALQUIER sede, para el administrador (el mesero solo ve la suya, en teselas).
    Ordenado por nombre con ordenamiento por mezcla (requisito de algoritmos funcionales del proyecto).
    """
    cashier_mode = get_rol_efectivo(request) == "CASHIER"
    sede = get_sede_efectiva(request) if cashier_mode else _sede_elegida(request, request.GET.get("sede"))
    query = request.GET.get("q", "").strip()
    sort_mode = request.GET.get("sort", "name")
    if sort_mode not in ("name", "quantity"):
        sort_mode = "name"
    filas = _filas_de_stock(sede, query) if sede else []
    if sort_mode == "quantity":
        # Stable Counting Sort: equal stock quantities retain name order.
        filas = counting_sort(filas, key=lambda row: row["actual"])
    return render(request, "inventario/stock_list.html", {
        "sedes": Sede.objects.filter(pk=sede.pk) if cashier_mode and sede else Sede.objects.filter(activo=True).order_by("nombre"),
        "cashier_mode": cashier_mode,
        "sede": sede, "query": query, "sort_mode": sort_mode,
        "filas": filas,
    })


@role_required("ADMIN", "CASHIER")
def stock_receive(request):
    """
    Registrar la ENTRADA de mercancía de una sede ("llegaron 30 Águila a Zona T, 10 a Galerías").
    Se elige la sede y se anotan las cantidades de todos los productos que llegaron. Es todo o nada:
    si una línea es inválida no se aplica ninguna. Cada entrada queda en la bitácora con el antes y el después.
    """
    cashier_mode = get_rol_efectivo(request) == "CASHIER"
    if cashier_mode:
        sede = get_sede_efectiva(request)
        if sede is None or not sede.activo:
            messages.error(request, "Choose a valid site.")
            return redirect("inventario:stock_list")
        # Reject forged POST site identifiers; never receive stock for another site.
        if request.method == "POST" and str(request.POST.get("sede", "")) != str(sede.pk):
            messages.error(request, "You can only receive stock at your assigned site.")
            return redirect("inventario:stock_receive")
    elif request.method == "POST":
        pk = _entero(request.POST.get("sede"))
        sede = Sede.objects.filter(activo=True, pk=pk).first() if pk is not None else None
    else:
        sede = _sede_elegida(request, request.GET.get("sede"))
    if sede is None:
        messages.error(request, "Choose a valid site.")
        return redirect("inventario:stock_list")

    filas = _filas_de_stock(sede)
    errores, entradas = [], []
    if request.method == "POST":
        for fila in filas:
            crudo = request.POST.get(f"qty_{fila['producto'].pk}", "").strip()
            fila["ingresado"] = crudo
            if crudo == "":
                continue
            if not re.fullmatch(r"[0-9]+", crudo):
                errores.append(f"{fila['producto'].nombre}: enter a whole number of units, 0 or more.")
                continue
            cantidad = int(crudo)
            if cantidad > MAX_ENTRADA:
                errores.append(f"{fila['producto'].nombre}: the maximum per delivery is {MAX_ENTRADA:,} units.")
            elif cantidad > 0:
                entradas.append((fila["producto"], cantidad))
        if not errores and not entradas:
            errores.append("Enter a quantity for at least one product.")

        if not errores:
            resumen = []
            with transaction.atomic():
                for producto, cantidad in entradas:
                    inv, _ = Inventario.objects.select_for_update().get_or_create(producto=producto, sede=sede)
                    antes = inv.cantidad
                    inv.cantidad = antes + cantidad
                    inv.save(update_fields=["cantidad"])
                    registrar(request, "STOCK_IN", "Inventario", inv,
                              f"{producto.nombre} +{cantidad} at {sede.nombre} ({antes} -> {inv.cantidad})")
                    resumen.append(f"{producto.nombre} +{cantidad}")
            messages.success(request, f"Stock received at {sede.nombre}: " + ", ".join(resumen) + ".")
            return redirect(f"{reverse('inventario:stock_list')}?sede={sede.pk}")
        for e in errores:
            messages.error(request, e)

    return render(request, "inventario/stock_receive.html", {
        "sedes": Sede.objects.filter(pk=sede.pk) if cashier_mode else Sede.objects.filter(activo=True).order_by("nombre"),
        "cashier_mode": cashier_mode, "sede": sede, "filas": filas,
    })


class _ExistenciaCambio(Exception):
    """La existencia cambió mientras el administrador editaba (por ejemplo, se vendió algo)."""


@role_required("ADMIN")
def stock_adjust(request):
    """
    HU044 — Corregir las existencias de una sede (conteo físico, pérdida, daño o error de digitación).
    Se escribe la cantidad REAL de cada producto que se quiere corregir y un motivo obligatorio.
    Es todo o nada. Como se deja una cantidad absoluta, si la existencia cambió mientras se editaba
    (por ejemplo, una venta) no se aplica nada y se avisa, para no pisar ese movimiento.
    """
    if request.method == "POST":
        pk = _entero(request.POST.get("sede"))
        sede = Sede.objects.filter(activo=True, pk=pk).first() if pk is not None else None
    else:
        sede = _sede_elegida(request, request.GET.get("sede"))
    if sede is None:
        messages.error(request, "Choose a valid site.")
        return redirect("inventario:stock_list")

    filas = _filas_de_stock(sede)
    motivo = ""
    if request.method == "POST":
        errores, cambios = [], []
        motivo = request.POST.get("motivo", "").strip()
        if len(motivo) < 3:
            errores.append("Write the reason for the adjustment (at least 3 characters).")
        elif len(motivo) > MAX_MOTIVO:
            errores.append(f"The reason can have at most {MAX_MOTIVO} characters.")
        for fila in filas:
            producto = fila["producto"]
            crudo = request.POST.get(f"new_{producto.pk}", "").strip()
            fila["ingresado"] = crudo
            visto = _entero(request.POST.get(f"seen_{producto.pk}"))
            if crudo == "":
                continue
            if not re.fullmatch(r"[0-9]+", crudo) or int(crudo) > MAX_EXISTENCIA:
                errores.append(f"{producto.nombre}: enter a whole number of units between 0 and {MAX_EXISTENCIA:,}.")
            elif visto is None:
                errores.append(f"{producto.nombre}: reload the page and try again.")
            elif int(crudo) != visto:  # igual a lo que se veía = sin cambio
                cambios.append((producto, int(crudo), visto))
        if not errores and not cambios:
            errores.append("Change the stock of at least one product.")

        if not errores:
            try:
                with transaction.atomic():
                    for producto, nuevo, visto in cambios:
                        inv, _ = Inventario.objects.select_for_update().get_or_create(producto=producto, sede=sede)
                        if inv.cantidad != visto:
                            raise _ExistenciaCambio(
                                f"{producto.nombre}: the stock changed while you were editing (now {inv.cantidad}). Review it and try again.")
                        antes = inv.cantidad
                        inv.cantidad = nuevo
                        inv.save(update_fields=["cantidad"])
                        registrar(request, "STOCK_ADJUST", "Inventario", inv,
                                  f"{producto.nombre} {antes} -> {nuevo} at {sede.nombre}. Reason: {motivo}")
                messages.success(request, f"Stock adjusted at {sede.nombre}: "
                                 + ", ".join(f"{p.nombre} {v} → {n}" for p, n, v in cambios) + ".")
                return redirect(f"{reverse('inventario:stock_list')}?sede={sede.pk}")
            except _ExistenciaCambio as e:
                errores.append(str(e))
                escrito = {f["producto"].pk: f["ingresado"] for f in filas}
                filas = _filas_de_stock(sede)  # con las existencias actuales
                for f in filas:
                    f["ingresado"] = escrito.get(f["producto"].pk, "")
        for e in errores:
            messages.error(request, e)

    return render(request, "inventario/stock_adjust.html", {
        "sedes": Sede.objects.filter(activo=True).order_by("nombre"), "sede": sede, "filas": filas, "motivo": motivo,
        "max_motivo": MAX_MOTIVO,
    })
