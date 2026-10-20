from datetime import datetime, time, timedelta

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from apps.usuarios.decorators import role_required
from apps.usuarios.models import Usuario

from .models import ACCIONES, Bitacora
from .utils import entero

POR_PAGINA = 25
CATEGORIAS = {"security": "Security events", "access": "Sign-ins and sign-outs", "change": "Changes"}


def _fecha(valor):
    try:
        return datetime.strptime(valor or "", "%Y-%m-%d").date()
    except ValueError:
        return None


def _inicio_del_dia(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min))


@role_required("ADMIN")
def bitacora_list(request):
    """
    Bitácora completa de auditoría (solo lectura), de la más reciente a la más antigua.
    Se puede filtrar por usuario, tipo de evento, acción, fechas y texto. Un valor de filtro
    inválido simplemente se ignora.
    """
    filtros = {k: request.GET.get(k, "").strip() for k in ("usuario", "categoria", "accion", "desde", "hasta", "q")}
    eventos = Bitacora.objects.select_related("usuario").order_by("-fecha", "-id")

    usuario = entero(filtros["usuario"])
    if usuario is not None:
        eventos = eventos.filter(usuario_id=usuario)
    if filtros["categoria"] in CATEGORIAS:
        de_acceso_o_seguridad = [a for a, (_, cat) in ACCIONES.items() if cat in ("access", "security")]
        if filtros["categoria"] == "change":
            eventos = eventos.exclude(accion__in=de_acceso_o_seguridad)
        else:
            eventos = eventos.filter(accion__in=[a for a, (_, cat) in ACCIONES.items() if cat == filtros["categoria"]])
    if filtros["accion"] in ACCIONES:
        eventos = eventos.filter(accion=filtros["accion"])
    # Rango de fechas con datetimes (no con __date): en MySQL __date necesita las tablas de zonas horarias cargadas.
    desde, hasta = _fecha(filtros["desde"]), _fecha(filtros["hasta"])
    if desde:
        eventos = eventos.filter(fecha__gte=_inicio_del_dia(desde))
    if hasta:
        eventos = eventos.filter(fecha__lt=_inicio_del_dia(hasta + timedelta(days=1)))
    if filtros["q"]:
        t = filtros["q"]
        eventos = eventos.filter(Q(detalle__icontains=t) | Q(entidad__icontains=t)
                                 | Q(usuario__username__icontains=t) | Q(usuario__nombre__icontains=t))

    pagina = Paginator(eventos, POR_PAGINA).get_page(request.GET.get("page"))
    consulta = request.GET.copy()
    consulta.pop("page", None)
    return render(request, "auditoria/bitacora_list.html", {
        "pagina": pagina,
        "filtros": filtros,
        "consulta": consulta.urlencode(),
        "usuarios": Usuario.objects.filter(bitacora__isnull=False).distinct().order_by("nombre"),
        "acciones": [(a, etiqueta) for a, (etiqueta, _) in ACCIONES.items()],
        "categorias": CATEGORIAS.items(),
    })
