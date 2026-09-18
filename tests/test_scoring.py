import unittest

from learningci.core.scoring import evaluate_scores


class ScoringTests(unittest.TestCase):
    def test_70_points_unlocks_route_even_with_old_dimension_gap(self):
        result = evaluate_scores({
            "explanation": 12,
            "prediction": 11,
            "implementation": 22,
            "diagnosis": 10,
            "transfer": 15,
        })
        self.assertTrue(result.passed)
        self.assertEqual(result.total, 70)
        self.assertFalse(result.mastered)
        self.assertIn("diagnosis 10 < 18", result.warnings)

    def test_69_points_still_needs_repair(self):
        result = evaluate_scores({
            "explanation": 10,
            "prediction": 10,
            "implementation": 20,
            "diagnosis": 15,
            "transfer": 14,
        })
        self.assertFalse(result.passed)
        self.assertEqual(result.total, 69)
        self.assertIn("total 69 < 70", result.failures)

    def test_80_plus_with_dimension_gates_is_mastered(self):
        result = evaluate_scores({
            "explanation": 12,
            "prediction": 12,
            "implementation": 22,
            "diagnosis": 20,
            "transfer": 15,
        })
        self.assertTrue(result.passed)
        self.assertTrue(result.mastered)
        self.assertEqual(result.total, 81)

    def test_80_plus_with_weak_dimension_advances_but_is_not_mastered(self):
        result = evaluate_scores({
            "explanation": 15,
            "prediction": 15,
            "implementation": 25,
            "diagnosis": 10,
            "transfer": 20,
        })
        self.assertTrue(result.passed)
        self.assertFalse(result.mastered)
        self.assertIn("diagnosis 10 < 18", result.warnings)


if __name__ == "__main__":
    unittest.main()
