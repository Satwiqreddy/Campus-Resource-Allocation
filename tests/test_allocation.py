"""T1, T5 and the search strategy."""
from environment.campus import make_model
from environment.scenarios import SCENARIOS


def run(name, strategy="astar"):
    return make_model(SCENARIOS[name], strategy).run()


def test_T1_available_venue_is_allocated():
    m = run("1. Normal allocation")
    a = m.allocations["Hackathon"]
    assert (a["venue"], a["start"], a["end"]) == ("Lab-1", 10, 13)
    assert len(a["volunteers"]) == 3 and a["equipment"] == ["Projector-1"] and not a["changes"]


def test_T5_multiple_simultaneous_events_coordinated():
    m = run("9. Full fest day (data/events.json)")
    assert not m.rejected and len(m.allocations) == 8
    assert m.conflicts() == []
    p = m.allocations["Prize Distribution"]
    assert p["start"] >= m.allocations["Hackathon"]["end"] and p["start"] >= m.allocations["Sports Event"]["end"]


def test_astar_beats_greedy_when_look_ahead_matters():
    a, g = run("8. Greedy vs A* (budget trade-off)"), run("8. Greedy vs A* (budget trade-off)", "greedy")
    assert len(a.allocations) == 2 and "IoT Workshop" in g.rejected
    assert a.metrics()["score"] > g.metrics()["score"]


def test_astar_never_worse_than_greedy_on_any_scenario():
    for name in SCENARIOS:
        assert run(name).metrics()["score"] >= run(name, "greedy").metrics()["score"] - 1e-9, name


def test_no_scenario_produces_double_booking():
    for name in SCENARIOS:
        assert run(name).conflicts() == [], name


def test_user_request_on_top_of_fest_day_updates_timetable():
    from environment.campus import fest_model, timetable
    vip = {"name": "VIP Keynote", "priority": 5, "participants": 150, "start": 10, "end": 12,
           "venue_types": ["hall"], "preferred_venue": "Seminar-Hall"}
    m = fest_model([vip])
    assert m.allocations["VIP Keynote"]["venue"] == "Seminar-Hall"      # outranks Art Exhibition (priority 1)
    assert "Art Exhibition" in m.allocations and m.conflicts() == []
    board = timetable(m)["venues"]["Seminar-Hall"]
    assert board[1] == "VIP Keynote" and None in board                 # 10:00 booked, some hour still free
