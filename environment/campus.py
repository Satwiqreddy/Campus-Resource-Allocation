"""The Mesa model: the campus environment, its agents and the message bus between them."""
import mesa

from agents.budget_agent import BudgetAgent
from agents.coordinator_agent import CoordinatorAgent
from agents.event_agent import EventAgent
from agents.resource_agent import ResourceAgent
from agents.volunteer_agent import VolunteerAgent
from algorithms.allocation import find_conflicts, score
from environment.resources import FEST_END, FEST_START, Equipment, EventRequest, Venue, Volunteer, load_json


class CampusModel(mesa.Model):
    def __init__(self, events, venues, equipment, volunteers, budget, committed=0, strategy="astar"):
        super().__init__()
        self.registry = {}   # agent name -> agent (the message bus address book)
        self.log = []        # (tick, Message) for every message sent and every reply
        self.tick = 0
        self.resource_agent = ResourceAgent(self, venues, equipment)
        self.volunteer_agent = VolunteerAgent(self, volunteers)
        self.budget_agent = BudgetAgent(self, budget, committed)
        self.coordinator = CoordinatorAgent(self, strategy)
        for e in events:
            if e.name in self.registry:
                raise ValueError(f"duplicate or reserved event name: {e.name}")
            EventAgent(self, e)

    def deliver(self, msg):
        if msg.receiver not in self.registry:
            raise ValueError(f"no agent named {msg.receiver}")
        self.log.append((self.tick, msg))
        reply = self.registry[msg.receiver].receive(msg)
        if reply is not None:
            self.log.append((self.tick, reply))
        return reply

    def step(self):
        """One time step: newly-arrived events submit requests, then the coordinator negotiates."""
        self.agents_by_type[EventAgent].do("step")
        self.coordinator.step()
        self.tick += 1

    def run(self):
        last = max((a.request.arrival for a in self.agents_by_type.get(EventAgent, [])), default=0)
        while self.tick <= last:
            self.step()
        return self

    # ---------------------------------------------------------------- results
    @property
    def allocations(self):
        return self.coordinator.allocations

    @property
    def rejected(self):
        return self.coordinator.rejected

    def conflicts(self):
        return find_conflicts(self.allocations)

    def metrics(self):
        return score(self.coordinator.requests.values(), self.allocations,
                     len(self.resource_agent.venues), self.budget_agent.total)


def make_model(spec, strategy="astar"):
    """Build a model from a scenario spec: {"events": [...]} plus optional overrides of the default campus."""
    res = load_json("resources.json")
    return CampusModel(
        events=[EventRequest(**e) for e in spec["events"]],
        venues=[Venue(**v) for v in spec.get("venues", res["venues"])],
        equipment=[Equipment(**e) for e in spec.get("equipment", res["equipment"])],
        volunteers=[Volunteer(**v) for v in spec.get("volunteers", load_json("volunteers.json"))],
        budget=spec.get("budget", res["budget"]),
        committed=spec.get("committed", 0),
        strategy=strategy,
    )


def fest_model(new_events=(), strategy="astar"):
    """The fest day from data/events.json, then each user request arriving one step later than the previous."""
    events = load_json("events.json") + [{**e, "arrival": i} for i, e in enumerate(new_events, 1)]
    return make_model({"events": events}, strategy).run()


def timetable(model):
    """What the agents currently hold, hour by hour: venue -> event (or None = free), plus free pools."""
    hours = list(range(FEST_START, FEST_END))
    ra, va = model.resource_agent, model.volunteer_agent
    venues = {v: [ra.holder(v, (h, h + 1)) for h in hours] for v in ra.venues}
    equipment = {t: [len(ra.free_ids(t, (h, h + 1))) for h in hours] for t in sorted(ra.unit_cost)}
    volunteers = {s: [len(va.free_ids(s, (h, h + 1))) for h in hours] for s in sorted(va.skills)}
    return dict(hours=hours, venues=venues, equipment=equipment, volunteers=volunteers)
