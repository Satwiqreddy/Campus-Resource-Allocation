# Campus Fest Resource Allocation — Multi-Agent System

Five kinds of autonomous agents (built on **Mesa**) negotiate venues, equipment, volunteers,
budget and time slots for a campus fest. The Coordinator owns **no** resources. It can only
learn availability by messaging the specialist agents, and they can refuse its commits.

```bash
pip install -r requirements.txt
python main.py          # all scenarios, summary
python main.py 6        # one scenario with the full agent conversation
python main.py book     # type your own events in the terminal; the agents book them
python -m streamlit run ui/app.py  # dashboard
python -m pytest -v     # automated tests
python -m uvicorn web.server:app   # website -> http://127.0.0.1:8000  (/#scenario-5 opens a scenario)
```

**Website ("The Fest Desk")** runs the real agents behind a FastAPI API. It shows today's programme
(happening now / upcoming / finished / not booked), a venue x hour free-slot board, free equipment
and volunteers, a booking slip for your own event, and an animated view of every message passed
between the five agents. **Streamlit** has the same live desk plus the review-scenario explorer.
Your own requests are replayed on top of `data/events.json`, one simulation step each.

**Slides:** `ppt/review1.tex` and `ppt/review2.tex` are self-contained Beamer files. Compile each with
`pdflatex` twice (or upload it to Overleaf).

## Agents

| Agent | Owns (private state) | Decides |
|---|---|---|
| 🎪 EventAgent (one per event) | its request, flexibility, private min-volunteer threshold | acceptable time windows, scores every option (deviation), ACCEPTs / REJECTs proposals |
| 📦 ResourceAgent | venue + equipment calendars | AVAILABLE / CONFLICT (+ holder) / ALTERNATIVE / UNAVAILABLE / ERROR, refuses double bookings |
| 👥 VolunteerAgent | volunteer rosters by skill | OFFER / INSUFFICIENT, borrows `general` volunteers on shortage |
| 💰 BudgetAgent | the ledger | APPROVE / REJECT per quote, refuses over-budget commits |
| 🧠 Coordinator | nothing | preemption, which options to combine (A*/greedy), re-planning after counter-offers |

## Negotiation protocol (one simulation step)

```
EventAgent  --REQUEST-->  Coordinator
Coordinator --QUERY-->    ResourceAgent   (venues/equipment for every acceptable window)
Coordinator --QUERY-->    VolunteerAgent  (offer per window, borrowing if short)
Coordinator --QUOTE-->    BudgetAgent     (which option costs fit)
Coordinator --EVALUATE--> EventAgent      (event scores its own options)
   if CONFLICT with a committed lower-priority event -> RELEASE + PREEMPT, re-plan it too
Coordinator: A* over all events of the batch  ->  PROPOSE to each EventAgent
   REJECT with a counter-constraint -> filter options, re-plan (max 5 rounds)
Coordinator --COMMIT-->   Resource / Volunteer / Budget agents (each may REFUSE -> rollback)
Coordinator --CONFIRM / DECLINE--> EventAgent
```

Events arrive at different steps (`arrival`), so the environment is dynamic.

## Search formulation

* **State**: events decided so far, each either an option (venue, slot, equipment, volunteers, cost) or REJECT.
* **Actions**: ALLOCATE an option (the options already include SWAPped venues and RESCHEDULEd slots), or REJECT. NEGOTIATE and preemption happen between searches.
* **Goal**: every event decided, with no venue/equipment/volunteer overlap, total cost within the budget and dependencies respected (`algorithms/constraints.py`).
* **Step cost** `g`: priority × deviation, where the event's own deviation score is venue change 2 (4 for a different venue type) + 3 per hour shifted + 10 × missing-volunteer fraction + cost/50 000. Rejecting costs 25 × priority.
* **Heuristic** `h`: for each undecided event, the cheaper of its best option and rejecting it, ignoring clashes. This is a relaxation, so it is admissible and A* returns the optimal plan.
* **Priority rule**: because deviation is multiplied by priority, displacing a priority-5 event costs 2.5× as much as displacing a priority-2 event, so the lower-priority event is the one that moves.
* **Baseline**: greedy (priority order, first feasible option). In scenario 8 greedy scores 0.465 and A* scores 0.855.

**Performance measure**: `Score = 0.15·U + 0.30·S + 0.30·P + 0.25·F − 1.0·C − 1.0·B`, where U = venue utilization, S = share of events scheduled, P = priority-weighted share scheduled, F = Jain fairness index of satisfaction, C = double bookings and B = budget overrun (`algorithms/allocation.py`).

## PEAS

| | |
|---|---|
| **P** | the score above: maximise utilization, events scheduled, priority satisfaction and fairness; minimise conflicts, budget overrun and cost |
| **E** | campus: venues, equipment, volunteers, budget, time slots (09:00–21:00), events arriving over time |
| **A** | allocate venue/equipment/volunteers, reserve slot, reject, reschedule, swap venue, preempt, propose/counter-propose |
| **S** | availability replies, event requirements, budget balance, volunteer rosters, priorities, conflict holders |

Environment: partially observable (each agent sees only its own state), deterministic, sequential, dynamic (arrivals), multi-agent, discrete, known.

## Test table (`python -m pytest -v`, 21 tests)

| Test | Input | Expected | Result |
|---|---|---|---|
| T1 | Available venue | Allocate Lab-1 10–13 | PASS |
| T2 | Same venue/time | Conflict detected, Robotics → Lab-2 | PASS |
| T3 | ₹15,000 request, ₹5,000 left | Budget REJECT, then cheaper Open-Air-Stage | PASS |
| T4 | 5 technical needed, 3 available | 3 + 1 borrowed general (80%) | PASS |
| T5 | Full fest, 8 events | All scheduled, 0 double bookings, dependencies held | PASS |
| T6 | Unknown resource / bad time | ERROR / ValueError | PASS |
| T7 | Zero budget | Reject | PASS |
| T8 | 4 events, 3 labs | Flexible event rescheduled 13–16 | PASS |
| + | Priority 5 arrives after priority 2 | Preempt, displaced event → Auditorium | PASS |
| + | Event rejects 50% volunteer offer | Coordinator re-plans, reschedules | PASS |
| + | A* vs greedy on every scenario | A* never worse | PASS |

## Layout

```
agents/       base (messages) + the 5 agents
algorithms/   astar.py, constraints.py, allocation.py (greedy, ordering, score)
environment/  campus.py (Mesa model + message bus), resources.py, scenarios.py
data/         events.json, resources.json, volunteers.json
tests/        pytest suites
ui/app.py     Streamlit dashboard
web/          FastAPI server + static website
ppt/          Review 1 and Review 2 Beamer decks
main.py       CLI demo
```
