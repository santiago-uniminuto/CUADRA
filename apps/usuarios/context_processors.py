from .decorators import get_actuando_como
from .models import Sede


def acting_mode(request):
    """
    Pone a disposición de TODAS las plantillas (vía base.html) el estado del
    modo actuación del admin, para dibujar en la barra superior el aviso y los
    botones "Act as" / "Return to Admin" sin repetirlo en cada vista.
    """
    if not request.user.is_authenticated or request.user.rol != "ADMIN":
        return {}
    actuando = get_actuando_como(request)
    if not actuando:
        return {"all_sedes": Sede.objects.filter(activo=True).order_by("nombre")}
    sede = Sede.objects.filter(pk=request.session.get("sede_activa_id")).first()
    return {
        "acting_as": actuando,
        "acting_as_display": "Waiter" if actuando == "WAITER" else "Cashier",
        "acting_sede": sede,
    }


# ---------------------------------------------------------------- Menú de navegación
# UNA sola lista por rol: cuando se construyan Pedidos, Pagos y Reportes (Sprint 4-5),
# solo hay que agregar aquí su entrada y aparece en el menú de quien corresponda.
MENU_POR_ROL = {
    "ADMIN": [
        ("Users", "usuarios:usuario_list"),
        ("Sites", "usuarios:sede_list"),
        ("Products", "catalogo:producto_list"),
        ("Suppliers", "catalogo:proveedor_list"),
        ("Product types", "catalogo:tipoproducto_list"),
        ("Inventory", "inventario:inventario_list"),
    ],
    "WAITER": [("Inventory", "inventario:inventario_list")],
    "CASHIER": [("Home", "autenticacion:home")],
}


def nav_menu(request):
    """Entradas del menú según el rol con el que se está operando (el admin que actúa ve el menú de ese rol)."""
    if not request.user.is_authenticated:
        return {}
    from django.urls import reverse
    from .decorators import get_rol_efectivo

    entradas = [{"label": label, "url": reverse(nombre)} for label, nombre in MENU_POR_ROL.get(get_rol_efectivo(request), [])]
    # La entrada activa es la de la ruta más específica que coincida (así /users/sedes/ no activa también "Users").
    coincidencias = [e for e in entradas if request.path.startswith(e["url"])]
    if coincidencias:
        max(coincidencias, key=lambda e: len(e["url"]))["active"] = True
    return {"nav_items": entradas}
