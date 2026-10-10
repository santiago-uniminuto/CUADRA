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
        return {"all_sedes": Sede.objects.order_by("nombre")}
    sede = Sede.objects.filter(pk=request.session.get("sede_activa_id")).first()
    return {
        "acting_as": actuando,
        "acting_as_display": "Waiter" if actuando == "WAITER" else "Cashier",
        "acting_sede": sede,
    }
