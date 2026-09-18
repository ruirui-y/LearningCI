from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

MAXIMUMS = {
    "explanation": 15,
    "prediction": 15,
    "implementation": 25,
    "diagnosis": 25,
    "transfer": 20,
}

# v0.3.11: formal verification no longer blocks the mainline on the old 80-point
# mastery bar. 70 points is enough to prove the node is usable and unlock the
# next node; 80 remains the mastery/stability target.
ROUTE_PASS_SCORE = 70
DEFAULT_MASTERY_SCORE = 80

# The old per-dimension gates are still valuable signals, but are advisory now.
# A weak dimension should be carried into issues/retests instead of trapping the
# learner in the same Recovery Zone node indefinitely.
DEFAULT_MINIMUMS = {
    "explanation": 10,
    "prediction": 10,
    "implementation": 20,
    "diagnosis": 18,
    "transfer": 14,
}


@dataclass(frozen=True)
class ScoreResult:
    total: int
    passed: bool
    mastered: bool
    failures: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def tier(self) -> str:
        if self.mastered:
            return "MASTERED"
        if self.passed:
            return "PASSED_WITH_WEAKNESSES"
        return "NEEDS_REPAIR"


def validate_scores(scores: Mapping[str, int]) -> None:
    for key, maximum in MAXIMUMS.items():
        if key not in scores:
            raise ValueError(f"missing score: {key}")
        value = int(scores[key])
        if value < 0 or value > maximum:
            raise ValueError(f"{key} must be between 0 and {maximum}")


def evaluate_scores(
    scores: Mapping[str, int],
    pass_score: int = ROUTE_PASS_SCORE,
    minimums: Mapping[str, int] | None = None,
    mastery_score: int = DEFAULT_MASTERY_SCORE,
) -> ScoreResult:
    """Evaluate a formal LearningCI score.

    v0.3.11 separates *route progression* from *stable mastery*:

    - ``total >= pass_score`` unlocks the next mainline node.
    - ``total >= mastery_score`` plus the old dimension minimums marks the score
      as stable/mastered.
    - dimension minimums below the mastery bar are warnings only; they no longer
      block mainline progression once the learner has 70+ overall.
    """
    validate_scores(scores)
    minimums = dict(DEFAULT_MINIMUMS if minimums is None else minimums)
    total = sum(int(scores[k]) for k in MAXIMUMS)

    failures: list[str] = []
    if total < int(pass_score):
        failures.append(f"total {total} < {pass_score}")

    warnings: list[str] = []
    for key, minimum in minimums.items():
        if int(scores[key]) < int(minimum):
            warnings.append(f"{key} {scores[key]} < {minimum}")

    passed = not failures
    mastered = passed and total >= int(mastery_score) and not warnings
    return ScoreResult(
        total=total,
        passed=passed,
        mastered=mastered,
        failures=tuple(failures),
        warnings=tuple(warnings),
    )
