import json
from pathlib import Path

RUBRIC_PATH = Path(__file__).parent / "rubric.json"


def load_rubric():
    """Read rubric.json and return it as a Python dictionary."""
    with open(RUBRIC_PATH, encoding="utf-8") as f:
        return json.load(f)


def match_percentage(scores, rubric):
    """
    scores: dict like {"problem": 4, "team": 2, ...} with values 1 to 5.
    Returns a number from 0 to 100.

    Each score is first turned into a fraction: 1 -> 0.0, 3 -> 0.5, 5 -> 1.0.
    Then every fraction is multiplied by its criterion's weight,
    added up, and divided by the total weight.
    """
    total_weight = 0
    earned = 0.0
    for c in rubric["criteria"]:
        score = scores[c["id"]]           # KeyError here means a criterion is missing
        if not 1 <= score <= 5:
            raise ValueError(f"{c['id']}: score must be 1 to 5, got {score}")
        earned += c["weight"] * (score - 1) / 4
        total_weight += c["weight"]
    return round(100 * earned / total_weight, 1)