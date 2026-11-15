import json
from statistics import mean, median
from db import db
from scoring import load_rubric, match_percentage


def collect(ids):
    decks = []
    with db() as conn:
        rows = conn.execute(
            """SELECT d.id, d.filename, s.source_url
               FROM decks d JOIN deck_sources s ON s.deck_id = d.id
               WHERE s.synthetic = 0"""
        ).fetchall()
        for d in rows:
            human = {r["criterion"]: r["score"] for r in conn.execute(
                "SELECT criterion, score FROM human_scores WHERE deck_id = ?", (d["id"],))}
            if set(human) != set(ids):
                continue                      # only fully scored decks count
            runs = []
            for r in conn.execute(
                    "SELECT id, result_json FROM runs "
                    "WHERE deck_id = ? AND status = 'done' ORDER BY saved_at", (d["id"],)):
                record = json.loads(r["result_json"])
                runs.append({
                    "run_id": r["id"],
                    "percent": record["percent"],
                    "scores": {c["id"]: c["score"] for c in record["result"]["criteria"]},
                })
            decks.append({"id": d["id"], "filename": d["filename"],
                          "source_url": d["source_url"], "human": human, "runs": runs})
    return decks


def agreement(pairs):
    """pairs: list of (human score, model score)."""
    if not pairs:
        return None
    n = len(pairs)
    return {
        "n": n,
        "exact_pct": round(100 * sum(h == m for h, m in pairs) / n, 1),
        "within1_pct": round(100 * sum(abs(h - m) <= 1 for h, m in pairs) / n, 1),
        "mae": round(mean(abs(h - m) for h, m in pairs), 2),
        "bias": round(mean(m - h for h, m in pairs), 2),   # + = model scores higher
    }


def evaluate():
    rubric = load_rubric()
    ids = [c["id"] for c in rubric["criteria"]]
    names = {c["id"]: c["name"] for c in rubric["criteria"]}
    decks = collect(ids)

    pairs, by_crit, same, spans, rows = [], {i: [] for i in ids}, [], [], []
    for d in decks:
        pcts = [r["percent"] for r in d["runs"]]
        for r in d["runs"]:
            for i in ids:
                pair = (d["human"][i], r["scores"][i])
                pairs.append(pair)
                by_crit[i].append(pair)
        if len(d["runs"]) >= 2:
            for i in ids:
                vals = [r["scores"][i] for r in d["runs"]]
                same.append(len(set(vals)) == 1)
                spans.append(max(vals) - min(vals))
        rows.append({
            "deck_id": d["id"], "filename": d["filename"], "source_url": d["source_url"],
            "runs": len(pcts),
            "human_percent": match_percentage(d["human"], rubric),
            "model_percents": pcts,
            "mean_model_percent": round(mean(pcts), 1) if pcts else None,
            "percent_range": round(max(pcts) - min(pcts), 1) if len(pcts) > 1 else None,
        })

    human_all = [d["human"][i] for d in decks for i in ids]
    baseline = None
    if human_all:
        const = median(human_all)
        baseline = {"constant": const,
                    "mae": round(mean(abs(h - const) for h in human_all), 2)}

    return {
        "n_decks": len(decks),
        "decks": rows,
        "overall": agreement(pairs),
        "baseline": baseline,
        "per_criterion": [{"id": i, "name": names[i], **(agreement(by_crit[i]) or {})}
                          for i in ids],
        "consistency": {
            "criteria_compared": len(same),
            "identical_pct": round(100 * sum(same) / len(same), 1) if same else None,
            "mean_score_range": round(mean(spans), 2) if spans else None,
        },
    }