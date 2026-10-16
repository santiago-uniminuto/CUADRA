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
# Cada entrada es (grupo, etiqueta, nombre de la URL). El grupo solo se dibuja en la barra lateral del admin.
MENU_POR_ROL = {
    "ADMIN": [
        ("Overview", "Dashboard", "reportes:dashboard"),
        ("Management", "Users", "usuarios:usuario_list"),
        ("Management", "Sites", "usuarios:sede_list"),
        ("Catalog", "Products", "catalogo:producto_list"),
        ("Catalog", "Suppliers", "catalogo:proveedor_list"),
        ("Catalog", "Product types", "catalogo:tipoproducto_list"),
        ("Operations", "Inventory", "inventario:stock_list"),
    ],
    "WAITER": [("", "Inventory", "inventario:inventario_list")],
    "CASHIER": [("", "Home", "autenticacion:home")],
}


def nav_menu(request):
    """
    Menú y tipo de interfaz según el rol con el que se está operando (el admin que actúa ve lo de ese rol):
      - layout "admin": panel de gestión (barra lateral, dashboard, informes).
      - layout "pos":   interfaz de punto de venta para mesero y cajero (oscura, botones grandes, táctil).
      - layout "guest": pantallas sin sesión (login).
    """
    if not request.user.is_authenticated:
        return {"layout": "guest"}
    from django.urls import reverse
    from .decorators import get_rol_efectivo, get_sede_efectiva

    rol = get_rol_efectivo(request)
    entradas = [{"group": grupo, "label": label, "url": reverse(nombre)} for grupo, label, nombre in MENU_POR_ROL.get(rol, [])]
    # La entrada activa es la de la ruta más específica que coincida (así /users/sedes/ no activa también "Users").
    coincidencias = [e for e in entradas if request.path.startswith(e["url"])]
    if coincidencias:
        max(coincidencias, key=lambda e: len(e["url"]))["active"] = True
    return {
        "nav_items": entradas,
        "layout": "admin" if rol == "ADMIN" else "pos",
        "sede_actual": get_sede_efectiva(request),
    }
