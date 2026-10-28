"""Coordinator Agent: collects proposals from the specialist agents, resolves conflicts, negotiates.

It owns no resources. Availability comes from ResourceAgent, volunteers from VolunteerAgent,
money from BudgetAgent and preferences from each EventAgent - all via messages. Its own
decisions are: preemption, which options to combine (A* / greedy), and handling counter-offers.
"""
from agents.base import CampusAgent, Message
from algorithms.allocation import REJECT_WEIGHT, greedy, search_order
from algorithms.astar import astar
from algorithms.constraints import Option, violation
from environment.resources import fmt, overlaps

MAX_ROUNDS = 5


class CoordinatorAgent(CampusAgent):
    def __init__(self, model, strategy="astar"):
        super().__init__(model, "Coordinator")
        self.strategy = strategy
        self.pending = {}       # event name -> REQUEST content
        self.requests = {}      # every request ever seen
        self.allocations = {}   # event name -> final allocation dict
        self.rejected = {}      # event name -> reason

    def note(self, text):
        self.model.log.append((self.model.tick, Message(self.name, "*", "NOTE", {}, text)))

    def on_request(self, msg):
        r = msg.content["request"]
        self.pending[r.name] = msg.content
        self.requests[r.name] = r
        self.rejected.pop(r.name, None)

    def step(self):
        if self.pending:
            batch, self.pending = self.pending, {}
            self.negotiate(batch)

    # ------------------------------------------------------------------ phases
    def negotiate(self, batch):
        options, reasons, holders = self.gather(batch)
        if self.preempt(batch, holders):
            options, reasons, _ = self.gather(batch)
        self.report_clashes(options)

        min_ratio, accepted = {}, set()
        for rnd in range(1, MAX_ROUNDS + 1):
            opts = {n: [o for o in options.get(n, []) if o.volunteer_ratio >= min_ratio.get(n, 0)] for n in batch}
            plan = self.plan(batch, opts, rnd)
            refused = False
            for name, o in plan.items():
                if o is None or o.key in accepted:
                    continue
                ans = self.send(name, "PROPOSE", f"{o.venue} {fmt(o.start, o.end)}, ₹{o.cost:,}, "
                                                 f"{o.volunteer_ratio:.0%} volunteers", option=o)
                if ans.performative == "ACCEPT":
                    accepted.add(o.key)
                else:
                    refused = True
                    min_ratio[name] = ans.content.get("min_volunteer_ratio", 1.01)
                    self.note(f"{name} counter-offered (min volunteers {min_ratio[name]:.0%}) - re-planning")
            if not refused:
                break
        else:
            plan = {n: (o if o and o.key in accepted else None) for n, o in plan.items()}

        for name in search_order([batch[n]["request"] for n in plan]):
            o = plan[name]
            if o is None:
                self.decline(name, reasons.get(name) or self.why_rejected(name, opts[name], plan))
            else:
                self.commit(name, o)

    def gather(self, batch):
        """Ask every specialist agent about every event; turn the answers into Options."""
        options, reasons, holders = {}, {}, {}
        for name, req in batch.items():
            r, windows = req["request"], req["windows"]
            res = self.send("ResourceAgent", "QUERY", f"venues/equipment for {name}", request=r, windows=windows)
            if res.performative == "ERROR":
                reasons[name] = res.text
                continue
            if res.content["holder"]:
                holders[name] = res.content["holder"]
            vol = self.send("VolunteerAgent", "QUERY", f"volunteers for {name}", request=r, windows=windows)
            if vol.performative == "ERROR":
                reasons[name] = vol.text
                continue
            cands = []
            for c in res.content["candidates"]:
                offer = vol.content["offers"][(c["start"], c["end"])]
                cands.append({**c, "cost": c["cost"] + r.extra_cost, "ratio": offer["ratio"],
                              "borrowed": offer["borrowed"],
                              "demand": {**r.equipment, **offer["demand"]},
                              "free": {**c["equipment_free"], **offer["free"]}})
            if not cands:
                reasons[name] = res.text
                continue
            bud = self.send("BudgetAgent", "QUOTE", f"cost check for {name}", event=name,
                            costs=[c["cost"] for c in cands])
            cands = [c for c, ok in zip(cands, bud.content["approved"]) if ok]
            if not cands:
                reasons[name] = f"budget: {bud.text}"
                continue
            if bud.performative == "REJECT":
                self.note(f"{name}: preferred option over budget - searching cheaper alternatives")
            ev = self.send(name, "EVALUATE", f"{len(cands)} feasible options", candidates=cands)
            options[name] = sorted(
                (Option(name, c["venue"], c["venue_type"], c["start"], c["end"], c["demand"], c["free"], c["cost"],
                        r.priority * d, d, c["ratio"], c["borrowed"])
                 for c, d in zip(cands, ev.content["deviations"])),
                key=lambda o: o.penalty)
        return options, reasons, holders

    def preempt(self, batch, holders):
        """A higher-priority newcomer may displace a committed lower-priority event (which is re-planned)."""
        done = False
        for name, holder in holders.items():
            if holder in self.allocations and self.requests[holder].priority < self.requests[name].priority:
                self.note(f"PREEMPT: {name} (priority {self.requests[name].priority}) outranks "
                          f"{holder} (priority {self.requests[holder].priority}); {holder} will be re-planned")
                for agent in ("ResourceAgent", "VolunteerAgent", "BudgetAgent"):
                    self.send(agent, "RELEASE", f"free everything held by {holder}", event=holder)
                self.send(holder, "PREEMPT", f"displaced by {name}; finding you an alternative")
                del self.allocations[holder]
                r = self.requests[holder]
                batch[holder] = {"request": r, "windows": self.model.registry[holder].windows()}
                done = True
        return done

    def report_clashes(self, options):
        tops = [os[0] for os in options.values() if os]
        for i, a in enumerate(tops):
            for b in tops[i + 1:]:
                if a.venue == b.venue and overlaps(a.window, b.window):
                    self.note(f"⚠ CONFLICT: {a.event} ({fmt(*a.window)}) and {b.event} ({fmt(*b.window)}) "
                              f"both want {a.venue}")

    def plan(self, batch, opts, rnd):
        order = search_order([batch[n]["request"] for n in batch])
        reject = {n: REJECT_WEIGHT * self.requests[n].priority for n in order}
        budget_left = self.send("BudgetAgent", "BALANCE", "how much is left?").content["remaining"]
        deps = {n: r.depends_on for n, r in self.requests.items()}
        fixed = {n: (a["start"], a["end"]) for n, a in self.allocations.items()}
        self._check = lambda o, assigned: violation(o, assigned, budget_left, deps, fixed)
        if self.strategy == "astar":
            plan, expanded = astar(order, opts, reject, self._check)
            how = f"A* expanded {expanded} states"
        else:
            plan, how = greedy(order, opts, self._check), "greedy, no look-ahead"
        cost = sum(o.penalty if o else reject[n] for n, o in plan.items())
        self.note(f"round {rnd}: plan cost {cost:.1f} ({how})")
        return plan

    def why_rejected(self, name, opts, plan):
        if not opts:
            return "no acceptable option left after negotiation"
        others = [o for n, o in plan.items() if o and n != name]
        return self._check(opts[0], others) or "rejecting was cheaper than displacing higher-priority events"

    def commit(self, name, o):
        r = self.requests[name]
        replies = [
            self.send("ResourceAgent", "COMMIT", f"book {o.venue} for {name}", event=name, venue=o.venue,
                      start=o.start, end=o.end, equipment=r.equipment),
            self.send("VolunteerAgent", "COMMIT", f"assign volunteers to {name}", event=name, start=o.start,
                      end=o.end, demand={k[4:]: v for k, v in o.demand.items() if k.startswith("vol:")}),
            self.send("BudgetAgent", "COMMIT", f"spend ₹{o.cost:,} on {name}", event=name, cost=o.cost),
        ]
        if any(m.performative == "REFUSE" for m in replies):
            for agent in ("ResourceAgent", "VolunteerAgent", "BudgetAgent"):
                self.send(agent, "RELEASE", f"roll back {name}", event=name)
            self.decline(name, "; ".join(m.text for m in replies if m.performative == "REFUSE"))
            return
        changes = []
        if r.preferred_venue and o.venue != r.preferred_venue:
            changes.append(f"venue {r.preferred_venue} → {o.venue}")
        elif o.venue_type != r.venue_types[0]:
            changes.append(f"venue type {r.venue_types[0]} → {o.venue_type} ({o.venue})")
        if o.start != r.start:
            changes.append(f"rescheduled {fmt(r.start, r.end)} → {fmt(o.start, o.end)}")
        if o.volunteer_ratio < 1 or o.borrowed:
            changes.append(f"volunteers {o.volunteer_ratio:.0%} of request"
                           + (f" ({o.borrowed} borrowed from general pool)" if o.borrowed else ""))
        alloc = dict(event=name, priority=r.priority, venue=o.venue, start=o.start, end=o.end,
                     equipment=replies[0].content["equipment"], volunteers=replies[1].content["volunteers"],
                     cost=o.cost, deviation=o.deviation, changes=changes)
        self.allocations[name] = alloc
        self.send(name, "CONFIRM", f"{o.venue} {fmt(o.start, o.end)}" + (f" ({'; '.join(changes)})" if changes else ""),
                  allocation=alloc)

    def decline(self, name, reason):
        self.rejected[name] = reason
        self.send(name, "DECLINE", reason)
