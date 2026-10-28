"""Domain objects of the campus environment and JSON loading."""
import json
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
FEST_START, FEST_END = 9, 21  # fest runs 09:00-21:00, time slots are whole hours


@dataclass
class EventRequest:
    name: str
    priority: int                      # 1 (low) .. 5 (critical)
    participants: int
    start: int                         # hour
    end: int                           # hour
    venue_types: list[str]             # acceptable venue types, most preferred first
    preferred_venue: str | None = None
    equipment: dict[str, int] = field(default_factory=dict)   # type -> count
    volunteers: dict[str, int] = field(default_factory=dict)  # skill -> count
    extra_cost: int = 0                # food, printing, prizes...
    flexible_hours: int = 0            # how far the event may be shifted in time
    min_volunteer_ratio: float = 1.0   # private: revealed only during negotiation
    depends_on: list[str] = field(default_factory=list)       # must start after these end
    arrival: int = 0                   # simulation step at which the request is submitted

    def __post_init__(self):
        if not 1 <= self.priority <= 5:
            raise ValueError(f"{self.name}: priority must be 1-5")
        if not FEST_START <= self.start < self.end <= FEST_END:
            raise ValueError(f"{self.name}: time must be within {FEST_START}:00-{FEST_END}:00 and start < end")
        if self.participants <= 0 or not self.venue_types:
            raise ValueError(f"{self.name}: needs participants > 0 and at least one venue type")
        if self.name in self.depends_on:
            raise ValueError(f"{self.name}: cannot depend on itself")


@dataclass
class Venue:
    id: str
    type: str
    capacity: int
    cost: int


@dataclass
class Equipment:
    id: str
    type: str
    cost: int


@dataclass
class Volunteer:
    id: str
    skill: str


def overlaps(a, b):
    """Half-open hour intervals (start, end) overlap?"""
    return a[0] < b[1] and b[0] < a[1]


def fmt(start, end):
    return f"{start:02d}:00-{end:02d}:00"


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))
