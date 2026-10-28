"""Greedy baseline, search ordering and the performance measure (PEAS 'P')."""
from environment.resources import FEST_END, FEST_START, overlaps

REJECT_WEIGHT = 25      # rejecting an event costs priority x 25 (worse than any single compromise)
WEIGHTS = dict(U=0.15, S=0.30, P=0.30, F=0.25, C=1.0, B=1.0)


def search_order(requests):
    """Highest priority first, but every dependency before its dependents."""
    by_name = {r.name: r for r in requests}
    out, seen = [], set()

    def visit(r):
        if r.name in seen:
            return
        seen.add(r.name)
        for d in r.depends_on:
            if d in by_name:
                visit(by_name[d])
        out.append(r.name)

    for r in sorted(requests, key=lambda r: -r.priority):
        visit(r)
    return out


def greedy(events, options, check):
    """Baseline: each event in order grabs its best still-feasible option. No look-ahead."""
    path = []
    for e in events:
        assigned = [o for o in path if o]
        path.append(next((o for o in options[e] if check(o, assigned) is None), None))
    return dict(zip(events, path))


def find_conflicts(allocations):
    """Double bookings in a final schedule (should always be empty)."""
    out = []
    items = list(allocations.values())
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if overlaps((a["start"], a["end"]), (b["start"], b["end"])):
                shared = ({a["venue"], *a["equipment"], *a["volunteers"]}
                          & {b["venue"], *b["equipment"], *b["volunteers"]})
                if shared:
                    out.append((a["event"], b["event"], sorted(shared)))
    return out


def score(requests, allocations, n_venues, budget_total):
    """Score = w1·U + w2·S + w3·P + w4·F − w5·C − w6·B  (all terms in 0..1 except C = conflict count)."""
    reqs = list(requests)
    booked_hours = sum(a["end"] - a["start"] for a in allocations.values())
    U = booked_hours / (n_venues * (FEST_END - FEST_START)) if n_venues else 0
    S = len(allocations) / len(reqs) if reqs else 1
    total_p = sum(r.priority for r in reqs)
    P = sum(r.priority for r in reqs if r.name in allocations) / total_p if total_p else 1
    sat = [max(0.0, 1 - allocations[r.name]["deviation"] / REJECT_WEIGHT) if r.name in allocations else 0.0
           for r in reqs]
    F = sum(sat) ** 2 / (len(sat) * sum(s * s for s in sat)) if any(sat) else 0   # Jain's fairness index
    C = len(find_conflicts(allocations))
    spent = sum(a["cost"] for a in allocations.values())
    B = max(0, spent - budget_total) / budget_total if budget_total else (1 if spent else 0)
    w = WEIGHTS
    total = w["U"] * U + w["S"] * S + w["P"] * P + w["F"] * F - w["C"] * C - w["B"] * B
    return dict(score=round(total, 3), U=round(U, 3), S=round(S, 3), P=round(P, 3), F=round(F, 3), C=C, B=round(B, 3))
