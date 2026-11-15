from scoring import load_rubric, match_percentage

rubric = load_rubric()
ids = [c["id"] for c in rubric["criteria"]]

# Check 1: weights add up to 100
assert sum(c["weight"] for c in rubric["criteria"]) == 100

# Check 2: all 1s -> 0%, all 5s -> 100%, all 3s -> 50%
assert match_percentage({i: 1 for i in ids}, rubric) == 0.0
assert match_percentage({i: 5 for i in ids}, rubric) == 100.0
assert match_percentage({i: 3 for i in ids}, rubric) == 50.0

# Check 3: a bad score is rejected
try:
    match_percentage({**{i: 3 for i in ids}, "team": 7}, rubric)
    raise SystemExit("FAIL: score of 7 was accepted")
except ValueError:
    pass

print("All checks passed. Criteria:", len(ids))