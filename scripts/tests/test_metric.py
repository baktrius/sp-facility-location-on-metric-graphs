"""Correspondence controls with changed metric ratios and graph topology."""

import sys
import unittest
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from metric import Unpaired, correspondence, normalize


def theta(lengths):
    vertices = ["a", "b"]
    edges = []
    for branch, length in enumerate(lengths):
        interior = [f"p{branch}_{i}" for i in range(1, length)]
        vertices.extend(interior)
        path = ["a", *interior, "b"]
        edges.extend([a, b] for a, b in pairwise(path))
    return {"vertices": vertices, "edges": edges}


class MetricTests(unittest.TestCase):
    def test_scale_and_labels(self):
        a, b = theta([2, 2, 4]), theta([4, 4, 8])
        b["vertices"].reverse()
        self.assertIsNotNone(correspondence(normalize(a), normalize(b)))

    def test_different_ratios(self):
        self.assertIsNone(
            correspondence(normalize(theta([2, 2, 4])), normalize(theta([2, 4, 4])))
        )

    def test_cycles_are_circles(self):
        def cycle(n):
            return {
                "vertices": [str(i) for i in range(n)],
                "edges": [[str(i), str((i + 1) % n)] for i in range(n)],
            }

        self.assertIsNotNone(correspondence(normalize(cycle(4)), normalize(cycle(16))))

    def test_resource_exhaustion_is_not_a_match(self):
        a = normalize(theta([2, 2, 4]))
        with self.assertRaises(Unpaired):
            correspondence(a, a, max_states=0)

    def test_bad_graph_refused(self):
        with self.assertRaises(Unpaired):
            normalize(
                {
                    "vertices": ["a", "b", "c"],
                    "edges": [["a", "b"], ["b", "c"], ["c", "a"]],
                }
            )


if __name__ == "__main__":
    unittest.main()
