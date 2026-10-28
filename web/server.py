"""Website backend:  python -m uvicorn web.server:app --reload   ->  http://127.0.0.1:8000"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from environment.campus import fest_model, make_model, timetable
from environment.resources import FEST_END, FEST_START, load_json
from environment.scenarios import SCENARIOS

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="Campus Fest Resource Desk")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class EventIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    priority: int = Field(ge=1, le=5)
    participants: int = Field(ge=1, le=5000)
    start: int
    end: int
    venue_types: list[str] = Field(min_length=1)
    preferred_venue: str | None = None
    equipment: dict[str, int] = {}
    volunteers: dict[str, int] = {}
    extra_cost: int = Field(0, ge=0)
    flexible_hours: int = Field(0, ge=0, le=6)
    min_volunteer_ratio: float = Field(1.0, ge=0, le=1)


class FestIn(BaseModel):
    requests: list[EventIn] = Field(default=[], max_length=20)
    strategy: str = "astar"


class ScenarioIn(BaseModel):
    name: str
    strategy: str = "astar"


def rows(model):
    out = []
    for name, r in model.coordinator.requests.items():
        a = model.allocations.get(name)
        out.append(dict(event=name, priority=r.priority, participants=r.participants,
                        requested=[r.start, r.end], booked=bool(a),
                        venue=a["venue"] if a else None, start=a["start"] if a else r.start,
                        end=a["end"] if a else r.end, equipment=a["equipment"] if a else [],
                        volunteers=a["volunteers"] if a else [], cost=a["cost"] if a else 0,
                        changes=a["changes"] if a else [], reason=model.rejected.get(name)))
    return sorted(out, key=lambda e: (e["start"], e["event"]))


def log(model, tick=None):
    return [dict(tick=t, sender=m.sender, receiver=m.receiver, performative=m.performative, text=m.text)
            for t, m in model.log if tick is None or t == tick]


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/meta")
def meta():
    res = load_json("resources.json")
    return dict(hours=[FEST_START, FEST_END], venues=res["venues"],
                venue_types=sorted({v["type"] for v in res["venues"]}),
                equipment=sorted({e["type"] for e in res["equipment"]}),
                skills=sorted({v["skill"] for v in load_json("volunteers.json")}),
                scenarios=list(SCENARIOS), budget=res["budget"])


@app.post("/api/fest")
def fest(body: FestIn):
    try:
        model = fest_model([r.model_dump() for r in body.requests], body.strategy)
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e))
    last = body.requests[-1].name if body.requests else None
    return dict(events=rows(model), board=timetable(model),
                log=log(model, len(body.requests) if last else 0), last=last,
                budget=dict(total=model.budget_agent.total, remaining=model.budget_agent.remaining))


@app.post("/api/scenario")
def scenario(body: ScenarioIn):
    if body.name not in SCENARIOS:
        raise HTTPException(404, "unknown scenario")
    model = make_model(SCENARIOS[body.name], body.strategy).run()
    other = make_model(SCENARIOS[body.name], "greedy" if body.strategy == "astar" else "astar").run()
    return dict(events=rows(model), log=log(model), metrics=model.metrics(), other=other.metrics(),
                budget=dict(total=model.budget_agent.total, remaining=model.budget_agent.remaining))
