"""T2, T3, T4, T6, T7, T8 + priority preemption and negotiation."""
import pytest

from environment.campus import make_model
from environment.scenarios import HACKATHON, SCENARIOS


def run(spec):
    return make_model(spec).run()


def notes(m):
    return " | ".join(msg.text for _, msg in m.log if msg.performative == "NOTE")


def test_T2_same_venue_same_time_conflict_resolved():
    m = run(SCENARIOS["2. Resource conflict"])
    assert "CONFLICT" in notes(m)
    assert m.allocations["Hackathon"]["venue"] == "Lab-1"          # higher priority keeps its choice
    assert m.allocations["Robotics Workshop"]["venue"] == "Lab-2"  # lower priority moved, not overwritten


def test_T3_insufficient_budget_finds_cheaper_alternative():
    m = run(SCENARIOS["3. Budget conflict"])
    assert any(msg.sender == "BudgetAgent" and msg.performative == "REJECT" for _, msg in m.log)
    a = m.allocations["Cultural Night"]
    assert a["venue"] == "Open-Air-Stage" and a["cost"] <= 5000
    assert m.budget_agent.remaining >= 0


def test_T4_volunteer_shortage_reduces_and_borrows():
    m = run(SCENARIOS["4. Volunteer shortage"])
    a = m.allocations["Hackathon"]
    assert len(a["volunteers"]) == 4 and "V06" in a["volunteers"]   # 3 technical + 1 borrowed general


def test_T6_invalid_resource_is_an_error():
    m = run({"events": [{**HACKATHON, "equipment": {"hologram": 1}}]})
    assert "unknown resource" in m.rejected["Hackathon"]
    with pytest.raises(ValueError):
        run({"events": [{**HACKATHON, "start": 22, "end": 23}]})


def test_T7_zero_budget_rejects_everything():
    m = run({"budget": 0, "events": [HACKATHON]})
    assert not m.allocations and "budget" in m.rejected["Hackathon"]


def test_T8_fully_occupied_labs_reschedules_flexible_event():
    m = run(SCENARIOS["7. Fully occupied labs (reschedule)"])
    assert len(m.allocations) == 4
    moved = m.allocations["Lab Session 4"]
    assert moved["start"] >= 13 and any("rescheduled" in c for c in moved["changes"])


def test_high_priority_event_preempts_and_displaced_event_gets_alternative():
    m = run(SCENARIOS["5. High-priority event (preemption)"])
    assert "PREEMPT" in notes(m)
    assert m.allocations["Keynote Talk"]["venue"] == "Seminar-Hall"
    assert m.allocations["Poetry Slam"]["venue"] == "Auditorium"


def test_counter_offer_triggers_replanning():
    m = run(SCENARIOS["6. Negotiation (counter-offer)"])
    assert any(msg.sender == "AI Workshop" and msg.performative == "REJECT" for _, msg in m.log)
    a = m.allocations["AI Workshop"]
    assert len(a["volunteers"]) == 4 and a["start"] == 13


def test_rejected_dependency_blocks_dependent_event():
    after = {"name": "Awards", "priority": 3, "participants": 50, "start": 15, "end": 16,
             "venue_types": ["classroom"], "depends_on": ["Hackathon"]}
    m = run({"events": [{**HACKATHON, "equipment": {"hologram": 1}}, after]})
    assert "Hackathon" in m.rejected and "depends on Hackathon" in m.rejected["Awards"]
