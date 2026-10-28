"""Resource Agent: owns venues + equipment calendars, never double-books."""
from agents.base import CampusAgent
from environment.resources import fmt, overlaps


class ResourceAgent(CampusAgent):
    def __init__(self, model, venues, equipment):
        super().__init__(model, "ResourceAgent")
        self.venues = {v.id: v for v in venues}
        self.equipment = {e.id: e for e in equipment}
        self.unit_cost = {e.type: e.cost for e in equipment}
        self.bookings = []   # (resource_id, start, end, event)

    def holder(self, rid, window):
        return next((ev for r, s, e, ev in self.bookings if r == rid and overlaps((s, e), window)), None)

    def free_ids(self, etype, window):
        return [e.id for e in self.equipment.values() if e.type == etype and not self.holder(e.id, window)]

    def on_query(self, msg):
        r, windows = msg.content["request"], msg.content["windows"]
        venue_types = {v.type for v in self.venues.values()}
        unknown = [t for t in r.venue_types if t not in venue_types]
        unknown += [t for t in r.equipment if t not in self.unit_cost]
        if r.preferred_venue and r.preferred_venue not in self.venues:
            unknown.append(r.preferred_venue)
        if unknown:
            return self.reply(msg, "ERROR", f"unknown resource(s): {', '.join(unknown)}")

        # preferred venue first, then by type preference, then cheapest
        venues = sorted((v for v in self.venues.values() if v.type in r.venue_types and v.capacity >= r.participants),
                        key=lambda v: (v.id != r.preferred_venue, r.venue_types.index(v.type), v.cost))
        equip_cost = sum(n * self.unit_cost[t] for t, n in r.equipment.items())
        candidates = []
        for w in windows:
            free = {t: len(self.free_ids(t, w)) for t in r.equipment}
            if any(free[t] < n for t, n in r.equipment.items()):
                continue
            candidates += [dict(venue=v.id, venue_type=v.type, start=w[0], end=w[1],
                                equipment_free=free, cost=v.cost + equip_cost)
                           for v in venues if not self.holder(v.id, w)]

        want = windows[0]
        holder = self.holder(r.preferred_venue, want) if r.preferred_venue else None
        first = candidates[0] if candidates else None
        if first and (first["start"], first["end"]) == want and first["venue_type"] == r.venue_types[0] \
                and (not r.preferred_venue or first["venue"] == r.preferred_venue):
            perf, text = "AVAILABLE", f"{first['venue']} free at {fmt(*want)}"
        elif holder:
            perf, text = "CONFLICT", f"{r.preferred_venue} already held by {holder} at {fmt(*want)}; {len(candidates)} alternatives"
        elif candidates:
            perf, text = "ALTERNATIVE", f"requested slot not possible; {len(candidates)} alternatives"
        else:
            perf, text = "UNAVAILABLE", "no venue/equipment free in any acceptable slot"
        return self.reply(msg, perf, text, candidates=candidates, holder=holder)

    def on_commit(self, msg):
        c = msg.content
        w = (c["start"], c["end"])
        if self.holder(c["venue"], w):
            return self.reply(msg, "REFUSE", f"{c['venue']} is no longer free")
        picked = []
        for t, n in c["equipment"].items():
            ids = self.free_ids(t, w)
            if len(ids) < n:
                return self.reply(msg, "REFUSE", f"only {len(ids)} {t} free")
            picked += ids[:n]
        self.bookings += [(rid, *w, c["event"]) for rid in [c["venue"], *picked]]
        return self.reply(msg, "ALLOCATED", f"{c['event']}: {c['venue']} + {', '.join(picked) or 'no equipment'}",
                          equipment=picked)

    def on_release(self, msg):
        self.bookings = [b for b in self.bookings if b[3] != msg.content["event"]]
