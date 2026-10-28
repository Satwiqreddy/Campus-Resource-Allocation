"""CLI demo: python main.py            -> run every scenario
             python main.py 3          -> run scenario 3 with the full agent conversation
             python main.py book       -> type in your own events; the agents book them on top of the fest day"""
import sys

from environment.campus import fest_model, make_model, timetable
from environment.resources import FEST_END, FEST_START, fmt, load_json
from environment.scenarios import SCENARIOS


def print_log(log):
    for tick, msg in log:
        print(f"  t{tick} {msg.sender:>16} → {msg.receiver:<16} {msg.performative:<12} {msg.text}")
    print()


def print_results(m, only=None):
    for a in m.allocations.values():
        if only is None or a["event"] in only:
            extra = f"  ({'; '.join(a['changes'])})" if a["changes"] else ""
            print(f"  ✓ {a['event']:<20} {a['venue']:<15} {fmt(a['start'], a['end'])}  ₹{a['cost']:,}{extra}")
    for n, why in m.rejected.items():
        if only is None or n in only:
            print(f"  ✗ {n:<20} {why}")


def show(name, verbose):
    print(f"\n=== {name} ===")
    m = make_model(SCENARIOS[name]).run()
    if verbose:
        print_log(m.log)
    print_results(m)
    g = make_model(SCENARIOS[name], "greedy").run().metrics()
    print(f"  score A* {m.metrics()['score']}  vs greedy {g['score']}")


# ------------------------------------------------------------------ interactive booking
def ask(prompt, default, cast=str, options=None):
    while True:
        raw = input(f"  {prompt} [{default}]: ").strip() or str(default)
        try:
            value = cast(raw)
        except ValueError:
            print("    ! not a valid value, try again")
            continue
        if options and value not in options:
            print(f"    ! choose one of: {', '.join(map(str, options))}")
            continue
        return value


def ask_counts(title, names):
    """'projector=1, microphone=2' -> {'projector': 1, 'microphone': 2}"""
    while True:
        raw = input(f"  {title} ({', '.join(names)}) e.g. {names[0]}=1 [none]: ").strip()
        try:
            counts = {k.strip(): int(v) for k, v in (p.split("=") for p in raw.split(",") if p.strip())}
        except ValueError:
            print("    ! write it as name=count, name=count")
            continue
        unknown = [k for k in counts if k not in names]
        if unknown:
            print(f"    ! unknown: {', '.join(unknown)}")
            continue
        return {k: v for k, v in counts.items() if v > 0}


def print_board(m):
    t = timetable(m)
    print("\n  Free (.) and booked (#) venues by hour")
    print("  " + " " * 15 + " ".join(f"{h:02d}" for h in t["hours"]))
    for venue, slots in t["venues"].items():
        print(f"  {venue:<15}" + " ".join(" #" if s else " ." for s in slots))
    print()


def book():
    res = load_json("resources.json")
    venues = [v["id"] for v in res["venues"]]
    venue_types = sorted({v["type"] for v in res["venues"]})
    equipment = sorted({e["type"] for e in res["equipment"]})
    skills = sorted({v["skill"] for v in load_json("volunteers.json")})
    mine = []

    m = fest_model()
    print("\n=== Today's fest day ===")
    print_results(m)
    print_board(m)

    while True:
        print("--- New event request (press Enter to accept the [default]) ---")
        new = dict(
            name=ask("Event name", f"My Event {len(mine) + 1}"),
            priority=ask("Priority 1-5", 3, int, range(1, 6)),
            participants=ask("Participants", 50, int),
            start=ask("Start hour", 14, int, range(FEST_START, FEST_END)),
            end=ask("End hour", 16, int, range(FEST_START + 1, FEST_END + 1)),
            venue_types=[t.strip() for t in ask(f"Venue types, preferred first ({', '.join(venue_types)})",
                                                "lab").split(",") if t.strip()],
            preferred_venue=ask("Specific venue (or 'none')", "none", str, venues + ["none"]),
            equipment=ask_counts("Equipment", equipment),
            volunteers=ask_counts("Volunteers", skills),
            extra_cost=ask("Other costs in ₹", 0, int),
            flexible_hours=ask("Can shift by how many hours", 1, int, range(0, 5)),
            min_volunteer_ratio=ask("Fewest volunteers you accept (0-1)", 1.0, float),
        )
        if new["preferred_venue"] == "none":
            new["preferred_venue"] = None
        try:
            m = fest_model(mine + [new])
        except (ValueError, TypeError) as e:
            print(f"\n  ✗ Invalid request: {e}\n")
            continue
        mine.append(new)
        print(f"\n=== How the five agents handled '{new['name']}' ===")
        print_log([(t, msg) for t, msg in m.log if t == len(mine)])
        print("=== Result ===")
        print_results(m, only=[r["name"] for r in mine])
        print_board(m)
        if input("Book another event? [y/N]: ").strip().lower() != "y":
            break


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    names = list(SCENARIOS)
    if len(sys.argv) > 1 and sys.argv[1] == "book":
        book()
    elif len(sys.argv) > 1:
        show(names[int(sys.argv[1]) - 1], verbose=True)
    else:
        for n in names:
            show(n, verbose=False)
