import unittest

from learningci.core.scoring import evaluate_scores


class ScoringTests(unittest.TestCase):
    def test_pass(self):
        result = evaluate_scores({
            "explanation": 12, "prediction": 12, "implementation": 22, "diagnosis": 20, "transfer": 15,
        })
        self.assertTrue(result.passed)
        self.assertEqual(result.total, 81)

    def test_dimension_gate_blocks_average(self):
        result = evaluate_scores({
            "explanation": 15, "prediction": 15, "implementation": 25, "diagnosis": 10, "transfer": 20,
        })
        self.assertFalse(result.passed)
        self.assertIn("diagnosis 10 < 18", result.failures)


if __name__ == "__main__":
    unittest.main()
