"""Event Agent: represents one fest event, submits its needs and judges offers."""
from agents.base import CampusAgent
from environment.resources import FEST_END, FEST_START, fmt


class EventAgent(CampusAgent):
    def __init__(self, model, request):
        super().__init__(model, request.name)
        self.request = request
        self.status = "waiting"     # waiting -> submitted -> allocated / rejected
        self.allocation = None

    def step(self):
        r = self.request
        if self.status == "waiting" and self.model.tick >= r.arrival:
            self.status = "submitted"
            self.send("Coordinator", "REQUEST",
                      f"{r.participants} people, {'/'.join(r.venue_types)}"
                      f"{' (' + r.preferred_venue + ')' if r.preferred_venue else ''}, "
                      f"{fmt(r.start, r.end)}, priority {r.priority}",
                      request=r, windows=self.windows())

    def windows(self):
        """Time windows this event accepts, preferred (unshifted) first."""
        r = self.request
        shifts = sorted(range(-r.flexible_hours, r.flexible_hours + 1), key=abs)
        return [(r.start + s, r.end + s) for s in shifts
                if FEST_START <= r.start + s and r.end + s <= FEST_END]

    def deviation(self, c):
        """How far a candidate is from what this event asked for (0 = exactly its request)."""
        r = self.request
        if c["venue"] == r.preferred_venue or (not r.preferred_venue and c["venue_type"] == r.venue_types[0]):
            d = 0
        elif c["venue_type"] == r.venue_types[0]:
            d = 2       # same kind of venue, different room
        else:
            d = 4       # fallback venue type
        d += 3 * abs(c["start"] - r.start)           # every hour shifted hurts
        d += 10 * (1 - c["ratio"])                   # missing volunteers
        return d + c["cost"] / 50000                 # cheaper breaks ties

    def on_evaluate(self, msg):
        cands = msg.content["candidates"]
        return self.reply(msg, "SCORES", f"scored {len(cands)} options",
                          deviations=[self.deviation(c) for c in cands])

    def on_propose(self, msg):
        o = msg.content["option"]
        need = self.request.min_volunteer_ratio
        if o.volunteer_ratio < need:
            return self.reply(msg, "REJECT",
                              f"only {o.volunteer_ratio:.0%} of volunteers, I need at least {need:.0%}",
                              min_volunteer_ratio=need)
        return self.reply(msg, "ACCEPT", f"{o.venue} {fmt(o.start, o.end)} is acceptable")

    def on_confirm(self, msg):
        self.status, self.allocation = "allocated", msg.content["allocation"]

    def on_decline(self, msg):
        self.status, self.allocation = "rejected", None

    def on_preempt(self, msg):
        self.status, self.allocation = "submitted", None
