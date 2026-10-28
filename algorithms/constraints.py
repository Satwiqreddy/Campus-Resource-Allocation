"""CSP side of the problem: what an option is and when two options clash."""
from dataclasses import dataclass

from environment.resources import overlaps


@dataclass
class Option:
    """One concrete way to host an event: venue + slot + pooled demand."""
    event: str
    venue: str
    venue_type: str
    start: int
    end: int
    demand: dict        # pooled resource -> count, e.g. {"projector": 1, "vol:technical": 3}
    free: dict          # pooled resource -> how many are free in this window (as reported by the agents)
    cost: int
    penalty: float      # priority x deviation, the A* step cost
    deviation: float
    volunteer_ratio: float = 1.0
    borrowed: int = 0

    @property
    def window(self):
        return (self.start, self.end)

    @property
    def key(self):
        return (self.event, self.venue, self.start)


def violation(o, assigned, budget_left, deps, fixed_times):
    """Why option `o` can't join the partial plan `assigned`, or None if it can.

    Pooled resources are checked against the sum of every overlapping assignment. Because
    pairwise-overlapping intervals share a common instant, the last-added member of any
    clique sees the whole clique, so the check is safe (slightly conservative).
    """
    over = [a for a in assigned if overlaps(a.window, o.window)]
    for a in over:
        if a.venue == o.venue:
            return f"{o.venue} taken by {a.event}"
    for res, need in o.demand.items():
        used = sum(a.demand.get(res, 0) for a in over)
        if used + need > o.free.get(res, 0):
            return f"not enough {res.removeprefix('vol:')} (needs {need}, {o.free.get(res, 0) - used} left)"
    if sum(a.cost for a in assigned) + o.cost > budget_left:
        return "over budget"
    times = {**fixed_times, **{a.event: a.window for a in assigned}}
    for d in deps.get(o.event, []):
        if d not in times:
            return f"depends on {d}, which is not scheduled"
        if times[d][1] > o.start:
            return f"must start after {d} ends"
    for a in assigned:
        if o.event in deps.get(a.event, []) and o.end > a.start:
            return f"must end before dependent {a.event} starts"
    return None
