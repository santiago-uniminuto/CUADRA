from django.shortcuts import render

from apps.usuarios.decorators import role_required

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
    """
    query = request.GET.get("q", "").strip()
    items = (
        Inventario.objects.select_related("producto")
        .filter(sede=request.user.sede)   # nunca de otra sede
        .order_by("producto__nombre")
    )
    if query:
        items = items.filter(producto__nombre__icontains=query)
    return render(request, "inventario/inventario_list.html", {"items": items, "query": query})
