"""Los algoritmos de ordenamiento hechos a mano deben dar el mismo resultado que sorted()."""
import random

from django.test import SimpleTestCase

from .ordenamiento import bubble_sort, insertion_sort, selection_sort

ALGORITMOS = [bubble_sort, selection_sort, insertion_sort]


class OrdenamientoTests(SimpleTestCase):
    def test_matches_sorted_on_random_lists(self):
        rnd = random.Random(2026)
        for algo in ALGORITMOS:
            for _ in range(60):
                datos = [rnd.randint(-50, 50) for _ in range(rnd.randint(0, 40))]
                self.assertEqual(algo(datos), sorted(datos), algo.__name__)

    def test_empty_single_and_already_sorted(self):
        for algo in ALGORITMOS:
            self.assertEqual(algo([]), [])
            self.assertEqual(algo([7]), [7])
            self.assertEqual(algo([1, 2, 3]), [1, 2, 3])
            self.assertEqual(algo([3, 2, 1]), [1, 2, 3])

    def test_does_not_mutate_the_input(self):
        for algo in ALGORITMOS:
            datos = [3, 1, 2]
            algo(datos)
            self.assertEqual(datos, [3, 1, 2])

    def test_sorts_objects_by_key_and_accepts_any_iterable(self):
        filas = [("Mojito", 18000), ("Corona", 5000), ("Margarita", 12000)]
        for algo in ALGORITMOS:
            resultado = algo(iter(filas), key=lambda f: f[1])
            self.assertEqual([f[0] for f in resultado], ["Corona", "Margarita", "Mojito"])

    def test_stable_algorithms_keep_the_original_order_of_ties(self):
        filas = [("a", 1), ("b", 1), ("c", 0), ("d", 1)]
        for algo in (bubble_sort, insertion_sort):  # la selección clásica no es estable
            resultado = algo(filas, key=lambda f: f[1])
            self.assertEqual([f[0] for f in resultado], ["c", "a", "b", "d"], algo.__name__)

    def test_selection_sort_with_a_composite_key_is_deterministic(self):
        filas = [("b", 1), ("a", 1), ("c", 0), ("d", 1)]
        for _ in range(5):
            resultado = selection_sort(filas, key=lambda f: (f[1], f[0]))
            self.assertEqual([f[0] for f in resultado], ["c", "a", "b", "d"])
