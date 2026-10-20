from django.db.models import Count, Q
from django.shortcuts import render

from apps.auditoria.models import Bitacora
from apps.catalogo.models import Producto, Proveedor, TipoProducto
from apps.usuarios.decorators import role_required
from apps.usuarios.models import Sede, Usuario


@role_required("ADMIN")
def dashboard(request):
    """
    Pantalla de inicio del administrador: bienvenida, resumen de lo que ya existe en el
    sistema, equipo por sede y últimas acciones de la bitácora. Las tarjetas de ventas y
    pedidos se agregan aquí cuando existan esos módulos (Sprint 4 y 5).
    """
    def tarjeta(etiqueta, modelo, url, campo="activo"):
        activos = modelo.objects.filter(**{campo: True}).count()
        inactivos = modelo.objects.filter(**{campo: False}).count()
        return {"label": etiqueta, "value": activos, "sub": f"{inactivos} inactive", "url": url}

    activos = Count("usuarios", filter=Q(usuarios__is_active=True))
    por_sede = (
        Sede.objects.filter(activo=True)
        .annotate(
            total=activos,
            meseros=Count("usuarios", filter=Q(usuarios__is_active=True, usuarios__rol=Usuario.Rol.MESERO)),
            cajeros=Count("usuarios", filter=Q(usuarios__is_active=True, usuarios__rol=Usuario.Rol.CAJERO)),
            admins=Count("usuarios", filter=Q(usuarios__is_active=True, usuarios__rol=Usuario.Rol.ADMIN)),
        )
        .order_by("nombre")
    )
    contexto = {
        "tarjetas": [
            tarjeta("Users", Usuario, "usuarios:usuario_list", campo="is_active"),
            tarjeta("Sites", Sede, "usuarios:sede_list"),
            tarjeta("Products", Producto, "catalogo:producto_list"),
            tarjeta("Suppliers", Proveedor, "catalogo:proveedor_list"),
            tarjeta("Product types", TipoProducto, "catalogo:tipoproducto_list"),
        ],
        "por_sede": por_sede,
        "recientes": Bitacora.objects.select_related("usuario").order_by("-fecha", "-id")[:10],
    }
    return render(request, "reportes/dashboard.html", contexto)
