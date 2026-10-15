from django.shortcuts import render

from apps.algoritmos.ordenamiento import insertion_sort
from apps.usuarios.decorators import get_sede_efectiva, role_required

from .models import Inventario


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
    académico de algoritmos), por cantidad disponible: primero lo que hay
    menos stock (a igual cantidad, por nombre), útil para que el mesero note
    rápido qué se está agotando.
    """
    query = request.GET.get("q", "").strip()
    sede = get_sede_efectiva(request)  # la propia, o la elegida si el admin actúa como mesero
    items_qs = Inventario.objects.select_related("producto__tipo_producto").filter(sede=sede, producto__activo=True)
    if query:
        items_qs = items_qs.filter(producto__nombre__icontains=query)
    items = insertion_sort(items_qs, key=lambda i: (i.cantidad, i.producto.nombre.lower()))
    return render(request, "inventario/inventario_list.html", {"items": items, "query": query, "sede": sede})
