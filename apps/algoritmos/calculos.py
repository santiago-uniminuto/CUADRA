"""
Algoritmos de cálculo vistos en clase, implementados a mano y usados por el sistema:

* sumatoria: total de un pedido (cajero, cola de pagos y detalle del pedido).
* desglose_vuelto (algoritmo voraz): billetes y monedas a devolver al cliente.
"""
from decimal import Decimal

from .ordenamiento import merge_sort

# Billetes y monedas de peso colombiano en circulación. Si cambia la
# denominación disponible en caja, solo se ajusta esta lista.
DENOMINACIONES_COP = (
    Decimal('100000'), Decimal('50000'), Decimal('20000'), Decimal('10000'),
    Decimal('5000'), Decimal('2000'), Decimal('1000'), Decimal('500'),
    Decimal('200'), Decimal('100'), Decimal('50'),
)


def sumatoria(valores, inicio=0):
    """
    Sumatoria: recorre los valores acumulando el total, de i = 1 hasta n.
    Recibe cualquier iterable (también un generador) y devuelve el mismo
    resultado que sum(). `inicio` fija el tipo del acumulador, por ejemplo
    Decimal('0.00') para dinero. Complejidad O(n).
    """
    total = inicio
    for valor in valores:
        total += valor
    return total


def desglose_vuelto(cambio, denominaciones=DENOMINACIONES_COP):
    """
    Algoritmo voraz (greedy): para devolver el cambio, en cada paso toma la
    mayor denominación que todavía cabe en lo que falta y repite hasta que no
    quepa ninguna. Con las denominaciones del peso colombiano (sistema
    canónico) esta decisión local da siempre la menor cantidad de billetes y
    monedas.

    Devuelve (desglose, resto): `desglose` es una lista de (denominación,
    cantidad) de mayor a menor, solo con las denominaciones usadas; `resto` es
    lo que no se puede entregar con la denominación más pequeña (por ejemplo
    centavos). Complejidad O(d), con d = número de denominaciones.
    """
    restante = Decimal(cambio)
    if not restante.is_finite() or restante < 0:
        raise ValueError('El cambio debe ser un valor finito mayor o igual a cero.')
    desglose = []
    for denominacion in merge_sort(denominaciones, key=lambda d: -d):
        cantidad = int(restante // denominacion)
        if cantidad:
            desglose.append((denominacion, cantidad))
            restante -= denominacion * cantidad
    return desglose, restante
