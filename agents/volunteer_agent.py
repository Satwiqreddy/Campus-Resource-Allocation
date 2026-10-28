"""Volunteer Agent: assigns volunteers by skill, borrows 'general' volunteers on shortage."""
from agents.base import CampusAgent
from environment.resources import fmt, overlaps


class VolunteerAgent(CampusAgent):
    def __init__(self, model, volunteers):
        super().__init__(model, "VolunteerAgent")
        self.volunteers = {v.id: v for v in volunteers}
        self.skills = {v.skill for v in volunteers}
        self.bookings = []   # (volunteer_id, start, end, event)

    def free_ids(self, skill, w):
        busy = {vid for vid, s, e, _ in self.bookings if overlaps((s, e), w)}
        return [v.id for v in self.volunteers.values() if v.skill == skill and v.id not in busy]

    def offer(self, needs, w):
        """Best this agent can do for `needs` in window w, borrowing general volunteers if short."""
        demand, free, short, borrowed = {}, {}, 0, 0
        general_free = len(self.free_ids("general", w))
        spare_general = general_free - min(needs.get("general", 0), general_free)
        for skill, n in needs.items():
            f = len(self.free_ids(skill, w))
            take = min(n, f)
            if take:
                demand[f"vol:{skill}"] = take
            free[f"vol:{skill}"] = f
            b = min(n - take, spare_general - borrowed) if skill != "general" else 0
            borrowed += b
            short += n - take - b
        if borrowed:
            demand["vol:general"] = demand.get("vol:general", 0) + borrowed
            free["vol:general"] = general_free
        total = sum(needs.values())
        return dict(demand=demand, free=free, borrowed=borrowed,
                    ratio=1.0 if total == 0 else (total - short) / total)

    def on_query(self, msg):
        r, windows = msg.content["request"], msg.content["windows"]
        unknown = [s for s in r.volunteers if s not in self.skills]
        if unknown:
            return self.reply(msg, "ERROR", f"no volunteers with skill(s): {', '.join(unknown)}")
        offers = {w: self.offer(r.volunteers, w) for w in windows}
        first = offers[windows[0]]
        if first["ratio"] == 1 and not first["borrowed"]:
            total = sum(r.volunteers.values())
            return self.reply(msg, "OFFER", f"all {total} volunteers available" if total else "no volunteers needed",
                              offers=offers)
        have = ", ".join(f"{first['free'][f'vol:{s}']}/{n} {s}" for s, n in r.volunteers.items())
        return self.reply(msg, "INSUFFICIENT",
                          f"at {fmt(*windows[0])} only {have} free; borrowing {first['borrowed']} general "
                          f"-> {first['ratio']:.0%} coverage", offers=offers)

    def on_commit(self, msg):
        c = msg.content
        w = (c["start"], c["end"])
        picked = []
        for skill, n in c["demand"].items():
            ids = self.free_ids(skill, w)
            if len(ids) < n:
                return self.reply(msg, "REFUSE", f"only {len(ids)} {skill} volunteers free")
            picked += ids[:n]
        self.bookings += [(vid, *w, c["event"]) for vid in picked]
        return self.reply(msg, "ASSIGNED", f"{c['event']}: {', '.join(picked) or 'none needed'}", volunteers=picked)

    def on_release(self, msg):
        self.bookings = [b for b in self.bookings if b[3] != msg.content["event"]]
