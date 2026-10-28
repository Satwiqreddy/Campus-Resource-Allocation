"""Each agent decides on its own, from its own state, via messages."""
from agents.base import Message
from environment.campus import make_model
from environment.scenarios import HACKATHON


def ask(model, receiver, performative, **content):
    return model.deliver(Message("Test", receiver, performative, content))


def test_resource_agent_refuses_double_booking():
    m = make_model({"events": []})
    book = dict(event="A", venue="Lab-1", start=10, end=13, equipment={"projector": 3})
    assert ask(m, "ResourceAgent", "COMMIT", **book).performative == "ALLOCATED"
    assert ask(m, "ResourceAgent", "COMMIT", **{**book, "event": "B"}).performative == "REFUSE"   # venue taken
    other = dict(book, event="C", venue="Lab-2", start=12, end=14, equipment={"projector": 1})
    assert ask(m, "ResourceAgent", "COMMIT", **other).performative == "REFUSE"                    # projectors gone


def test_resource_agent_reports_conflict_holder():
    m = make_model({"events": [HACKATHON]}).run()
    r = m.registry["Hackathon"].request
    reply = ask(m, "ResourceAgent", "QUERY", request=r, windows=[(11, 14)])
    assert reply.performative == "CONFLICT" and reply.content["holder"] == "Hackathon"


def test_volunteer_agent_borrows_general_on_shortage():
    m = make_model({"events": [], "volunteers": [{"id": "V1", "skill": "technical"}, {"id": "V2", "skill": "general"}]})
    offer = m.volunteer_agent.offer({"technical": 3}, (10, 12))
    assert offer["borrowed"] == 1 and abs(offer["ratio"] - 2 / 3) < 1e-9


def test_budget_agent_rejects_over_budget():
    m = make_model({"events": [], "budget": 50000, "committed": 45000})
    reply = ask(m, "BudgetAgent", "QUOTE", event="X", costs=[15000, 4000])
    assert reply.performative == "REJECT" and reply.content["approved"] == [False, True]


def test_event_agent_rejects_offer_below_its_private_threshold():
    m = make_model({"events": [{**HACKATHON, "min_volunteer_ratio": 0.9}]})
    o = type("O", (), {"volunteer_ratio": 0.5, "venue": "Lab-1", "start": 10, "end": 13})()
    reply = ask(m, "Hackathon", "PROPOSE", option=o)
    assert reply.performative == "REJECT" and reply.content["min_volunteer_ratio"] == 0.9


def test_agents_communicate_only_through_messages():
    m = make_model({"events": [HACKATHON]}).run()
    senders = {msg.sender for _, msg in m.log}
    assert {"Hackathon", "Coordinator", "ResourceAgent", "VolunteerAgent", "BudgetAgent"} <= senders
