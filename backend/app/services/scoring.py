"""Transparent, configurable risk indicator.

risk = min(100, sum(severity_points[f.severity] * factor_weight[f.factor]) for every finding)

This is an internal prototype indicator for prioritising review. It is not a calibrated probability
of fraud and not an official AICTE score.
"""

DEFAULT_SCORING = {
    "severity_points": {"critical": 40, "high": 25, "medium": 12, "low": 4, "info": 0},
    "factor_weights": {"missing_evidence": 1.0, "expired": 1.0, "flags": 1.0, "review": 1.0,
                       "uncertain": 1.0, "screening": 0.5},
    "bands": {"medium": 25, "high": 60},
}

FACTOR_LABELS = {
    "missing_evidence": "Missing evidence",
    "expired": "Expired documents",
    "flags": "Compliance violations / inconsistencies",
    "review": "Fields or statements needing review",
    "uncertain": "Uncertain extraction",
    "screening": "Authenticity-screening signals",
}

DISCLAIMER = ("Internal prototype risk indicator for prioritising human review. Not a calibrated probability "
              "of fraud and not an official AICTE score.")


def compute(findings: list[dict], config: dict) -> dict:
    sp, fw = config["severity_points"], config["factor_weights"]
    factors = {k: {"label": v, "count": 0, "points": 0.0} for k, v in FACTOR_LABELS.items()}
    items = []
    total = 0.0
    for f in findings:
        pts = float(sp.get(f["severity"], 0)) * float(fw.get(f["factor"], 1.0))
        total += pts
        fac = factors.setdefault(f["factor"], {"label": f["factor"], "count": 0, "points": 0.0})
        fac["count"] += 1
        fac["points"] = round(fac["points"] + pts, 1)
        items.append({"finding_id": f.get("id"), "rule_id": f["rule_id"], "severity": f["severity"],
                      "factor": f["factor"], "points": round(pts, 1), "title": f["title"]})
    score = min(100, round(total))
    bands = config["bands"]
    band = "High" if score >= bands["high"] else "Medium" if score >= bands["medium"] else "Low"
    return {
        "score": score, "band": band, "raw_total": round(total, 1), "factors": factors, "items": items,
        "formula": "risk = min(100, Σ severity_points × factor_weight)",
        "severity_points": sp, "factor_weights": fw, "bands": bands, "disclaimer": DISCLAIMER,
    }
