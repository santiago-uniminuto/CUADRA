"""
Algoritmos de ordenamiento, implementados manualmente (sin usar sort()/order_by()
de Django ni de Python) para el requisito académico de la materia.

Todas las funciones reciben cualquier iterable (incluido un QuerySet de Django,
que se convierte a lista antes de ordenar: no se modifica ni se vuelve a
consultar la base de datos) y una función `key` que indica por qué campo
ordenar, igual que la función sort() nativa de Python, pero implementadas a
mano. No mutan la lista/QuerySet original: siempre devuelven una lista nueva.
"""


def bubble_sort(items, key=lambda x: x):
    """
    Ordenamiento burbuja: en cada pasada compara elementos adyacentes y los
    intercambia si están en el orden incorrecto. Si una pasada completa no
    hace ningún intercambio, la lista ya está ordenada y se corta antes
    (optimización típica de burbuja). Complejidad O(n²).
    """
    data = list(items)
    n = len(data)
    for i in range(n - 1):
        hubo_intercambio = False
        for j in range(n - 1 - i):
            if key(data[j]) > key(data[j + 1]):
                data[j], data[j + 1] = data[j + 1], data[j]
                hubo_intercambio = True
        if not hubo_intercambio:
            break
    return data


def selection_sort(items, key=lambda x: x):
    """
    Ordenamiento por selección: en cada pasada busca el elemento más pequeño
    del resto de la lista y lo intercambia a su posición final. Complejidad
    O(n²), con menos intercambios que burbuja (uno por pasada como máximo).
    OJO: la selección clásica NO es estable (elementos con la misma clave pueden
    cambiar de orden entre sí); por eso quien la use debe poner una clave
    compuesta que desempate, p. ej. (precio, nombre).
    """
    data = list(items)
    n = len(data)
    for i in range(n - 1):
        indice_minimo = i
        for j in range(i + 1, n):
            if key(data[j]) < key(data[indice_minimo]):
                indice_minimo = j
        if indice_minimo != i:
            data[i], data[indice_minimo] = data[indice_minimo], data[i]
    return data


def insertion_sort(items, key=lambda x: x):
    """
    Ordenamiento por inserción: toma cada elemento y lo desplaza hacia atrás
    hasta encontrar su posición correcta dentro de la parte ya ordenada de la
    lista. Complejidad O(n²), pero muy eficiente cuando los datos ya están
    casi ordenados (caso frecuente en listas pequeñas como el inventario).
    """
    data = list(items)
    for i in range(1, len(data)):
        actual = data[i]
        j = i - 1
        while j >= 0 and key(data[j]) > key(actual):
            data[j + 1] = data[j]
            j -= 1
        data[j + 1] = actual
    return data


def merge_sort(items, key=lambda x: x):
    """
    Ordenamiento por mezcla (divide y vencerás): parte la lista por la mitad, ordena cada
    mitad recursivamente y las mezcla. Complejidad O(n log n), mucho mejor que los
    anteriores cuando la lista crece (p. ej. el inventario de varias sedes o un reporte).
    Es estable: los elementos con la misma clave conservan su orden original.
    """
    data = list(items)
    if len(data) <= 1:
        return data
    mitad = len(data) // 2
    return _mezclar(merge_sort(data[:mitad], key), merge_sort(data[mitad:], key), key)


def _mezclar(izquierda, derecha, key):
    """Une dos listas ya ordenadas en una sola, tomando siempre el menor de los dos frentes."""
    resultado, i, j = [], 0, 0
    while i < len(izquierda) and j < len(derecha):
        if key(derecha[j]) < key(izquierda[i]):
            resultado.append(derecha[j])
            j += 1
        else:  # empate: sale primero el de la izquierda (así es estable)
            resultado.append(izquierda[i])
            i += 1
    resultado.extend(izquierda[i:])
    resultado.extend(derecha[j:])
    return resultado
