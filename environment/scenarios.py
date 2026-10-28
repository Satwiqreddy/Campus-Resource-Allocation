"""The Review-2 demo scenarios. Each is a spec for environment.campus.make_model."""
from environment.resources import load_json

HACKATHON = {"name": "Hackathon", "priority": 5, "participants": 120, "start": 10, "end": 13,
             "venue_types": ["lab"], "preferred_venue": "Lab-1",
             "equipment": {"projector": 1}, "volunteers": {"technical": 3}, "extra_cost": 2000}

SCENARIOS = {
    "1. Normal allocation": {
        "events": [HACKATHON],
    },
    "2. Resource conflict": {
        "events": [HACKATHON,
                   {"name": "Robotics Workshop", "priority": 4, "participants": 80, "start": 11, "end": 14,
                    "venue_types": ["lab"], "preferred_venue": "Lab-1", "equipment": {"projector": 1},
                    "volunteers": {"technical": 2}, "flexible_hours": 2}],
    },
    "3. Budget conflict": {
        "budget": 50000, "committed": 45000,
        "events": [{"name": "Cultural Night", "priority": 5, "participants": 500, "start": 18, "end": 21,
                    "venue_types": ["stage"], "preferred_venue": "Main-Stage",
                    "equipment": {"microphone": 2, "speaker": 1}, "extra_cost": 800}],
    },
    "4. Volunteer shortage": {
        "volunteers": [{"id": "V01", "skill": "technical"}, {"id": "V04", "skill": "technical"},
                       {"id": "V07", "skill": "technical"}, {"id": "V06", "skill": "general"}],
        "events": [{**HACKATHON, "volunteers": {"technical": 5}, "min_volunteer_ratio": 0.6}],
    },
    "5. High-priority event (preemption)": {
        "events": [{"name": "Poetry Slam", "priority": 2, "participants": 150, "start": 14, "end": 16,
                    "venue_types": ["hall"], "preferred_venue": "Seminar-Hall", "equipment": {"microphone": 1},
                    "arrival": 0},
                   {"name": "Keynote Talk", "priority": 5, "participants": 180, "start": 14, "end": 16,
                    "venue_types": ["hall"], "preferred_venue": "Seminar-Hall",
                    "equipment": {"microphone": 1, "projector": 1}, "arrival": 1}],
    },
    "6. Negotiation (counter-offer)": {
        "volunteers": [{"id": f"V0{i}", "skill": "technical"} for i in range(1, 6)],
        "events": [{"name": "Drone Workshop", "priority": 5, "participants": 50, "start": 10, "end": 13,
                    "venue_types": ["lab"], "preferred_venue": "Lab-1", "volunteers": {"technical": 3}},
                   {"name": "AI Workshop", "priority": 3, "participants": 50, "start": 10, "end": 12,
                    "venue_types": ["lab"], "volunteers": {"technical": 4}, "min_volunteer_ratio": 0.9,
                    "flexible_hours": 3, "arrival": 1}],
    },
    "7. Fully occupied labs (reschedule)": {
        "events": [{"name": f"Lab Session {i}", "priority": p, "participants": 50, "start": 10, "end": 13,
                    "venue_types": ["lab"], "flexible_hours": f}
                   for i, (p, f) in enumerate([(5, 0), (4, 0), (4, 0), (2, 3)], 1)],
    },
    "8. Greedy vs A* (budget trade-off)": {
        "budget": 16000,
        "events": [{"name": "Tech Talk", "priority": 5, "participants": 150, "start": 14, "end": 16,
                    "venue_types": ["hall"], "preferred_venue": "Auditorium"},
                   {"name": "IoT Workshop", "priority": 3, "participants": 100, "start": 10, "end": 12,
                    "venue_types": ["lab"], "extra_cost": 2000}],
    },
    "9. Full fest day (data/events.json)": {
        "events": load_json("events.json"),
    },
}
