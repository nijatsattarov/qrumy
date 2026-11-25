"""Customer-experience scores. Pure functions over lists of integer answers."""


def nps(values: list[int]) -> dict | None:
    """Net Promoter Score: % promoters (9–10) minus % detractors (0–6). Range −100…100."""
    if not values:
        return None
    n = len(values)
    promoters = sum(1 for v in values if v >= 9)
    detractors = sum(1 for v in values if v <= 6)
    passives = n - promoters - detractors
    return {"score": round((promoters - detractors) * 100 / n), "n": n,
            "promoters": promoters, "passives": passives, "detractors": detractors,
            "promoters_pct": round(promoters * 100 / n), "passives_pct": round(passives * 100 / n),
            "detractors_pct": round(detractors * 100 / n)}


def csat(values: list[int]) -> dict | None:
    """CSAT: share of satisfied answers (4–5 on a 1–5 scale), in %."""
    if not values:
        return None
    satisfied = sum(1 for v in values if v >= 4)
    return {"score": round(satisfied * 100 / len(values)), "n": len(values),
            "average": round(sum(values) / len(values), 2)}


def ces(values: list[int]) -> dict | None:
    """CES: average effort on a 1–7 scale (higher = easier) and % of easy answers (5–7)."""
    if not values:
        return None
    easy = sum(1 for v in values if v >= 5)
    return {"score": round(sum(values) / len(values), 1), "n": len(values),
            "easy_pct": round(easy * 100 / len(values))}


def average(values: list[int]) -> dict | None:
    if not values:
        return None
    return {"score": round(sum(values) / len(values), 1), "n": len(values)}
