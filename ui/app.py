"""Streamlit dashboard:  python -m streamlit run ui/app.py"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt
import pandas as pd
import streamlit as st

from environment.campus import fest_model, make_model, timetable
from environment.resources import FEST_END, FEST_START, fmt, load_json
from environment.scenarios import SCENARIOS

st.set_page_config(page_title="Campus Fest Allocation", page_icon="🎪", layout="wide")
st.title("🎪 Campus Fest Resource Allocation — Multi-Agent System")

if "my_events" not in st.session_state:
    st.session_state.my_events = []

mode = st.sidebar.radio("View", ["Live fest desk", "Review scenarios"])
strategy = st.sidebar.radio("Coordinator search strategy", ["astar", "greedy"],
                            format_func={"astar": "A* (optimal)", "greedy": "Greedy (baseline)"}.get)


def conversation(log, tick=None):
    rows = [{"Step": t, "From": m.sender, "To": m.receiver, "Performative": m.performative, "Message": m.text}
            for t, m in log if tick is None or t == tick]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=480)


def allocation_table(model, now=None):
    def status(name):
        if name in model.rejected:
            return "not booked"
        a = model.allocations[name]
        if now is None:
            return "booked"
        return "finished" if a["end"] <= now else "happening now" if a["start"] <= now else "upcoming"

    rows = []
    for name, r in model.coordinator.requests.items():
        a = model.allocations.get(name)
        rows.append({"Status": status(name), "Event": name, "Priority": r.priority,
                     "Venue": a["venue"] if a else "—", "Time": fmt(a["start"], a["end"]) if a else fmt(r.start, r.end),
                     "Equipment": ", ".join(a["equipment"]) if a else "",
                     "Volunteers": ", ".join(a["volunteers"]) if a else "",
                     "Cost (₹)": a["cost"] if a else 0,
                     "Notes": ("; ".join(a["changes"]) or "as requested") if a else model.rejected[name]})
    order = {"happening now": 0, "upcoming": 1, "booked": 1, "finished": 2, "not booked": 3}
    rows.sort(key=lambda row: (order[row["Status"]], row["Time"]))
    colors = {"happening now": "background-color: #d7f0dd", "upcoming": "background-color: #dde8f8",
              "not booked": "background-color: #f8dcdc"}
    st.dataframe(pd.DataFrame(rows).style.map(lambda v: colors.get(v, ""), subset=["Status"]),
                 hide_index=True, width="stretch")


def free_board(model, now=None):
    t = timetable(model)
    cols = [f"{h:02d}" for h in t["hours"]]
    grid = pd.DataFrame({v: [e or "free" for e in slots] for v, slots in t["venues"].items()}, index=cols).T
    style = grid.style.map(lambda v: "color: #1b7a3a" if v == "free" else "background-color: #2a78d6; color: white")
    if now is not None and f"{now:02d}" in cols:
        style = style.set_properties(subset=[f"{now:02d}"], **{"border-left": "3px solid #d9480f"})
    st.markdown("**Venues** — booked (blue) vs free, by starting hour")
    st.dataframe(style, width="stretch")
    c1, c2 = st.columns(2)
    c1.markdown("**Equipment free** per hour")
    c1.dataframe(pd.DataFrame(t["equipment"], index=cols).T, width="stretch")
    c2.markdown("**Volunteers free** per hour")
    c2.dataframe(pd.DataFrame(t["volunteers"], index=cols).T, width="stretch")


# ------------------------------------------------------------------ live fest desk
if mode == "Live fest desk":
    model = fest_model(st.session_state.my_events, strategy)
    now = st.sidebar.slider("Current time", FEST_START, FEST_END,
                            min(max(datetime.now().hour, FEST_START), FEST_END), format="%d:00")
    spent = model.budget_agent.total - model.budget_agent.remaining
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Events booked", f"{len(model.allocations)} / {len(model.coordinator.requests)}")
    c2.metric("Happening now", sum(a["start"] <= now < a["end"] for a in model.allocations.values()))
    c3.metric("Budget used", f"₹{spent:,}", f"₹{model.budget_agent.remaining:,} left", delta_color="off")
    c4.metric("Your requests", len(st.session_state.my_events))

    tab_events, tab_free, tab_book = st.tabs(["All events", "Free slots", "Book your event"])
    with tab_events:
        allocation_table(model, now)
    with tab_free:
        free_board(model, now)

    with tab_book:
        res = load_json("resources.json")
        venue_types = sorted({v["type"] for v in res["venues"]})
        equip_types = sorted({e["type"] for e in res["equipment"]})
        skills = sorted({v["skill"] for v in load_json("volunteers.json")})
        with st.form("book"):
            a, b, c = st.columns(3)
            name = a.text_input("Event name", "My Workshop")
            priority = b.slider("Priority", 1, 5, 3)
            participants = c.number_input("Participants", 1, 2000, 60)
            start, end = a.select_slider("Time", options=list(range(FEST_START, FEST_END + 1)), value=(14, 16),
                                         format_func=lambda h: f"{h}:00")
            types = b.multiselect("Acceptable venue types (first = preferred)", venue_types, ["lab"])
            pref = c.selectbox("Preferred venue (optional)", ["—"] + [v["id"] for v in res["venues"]])
            st.markdown("**Equipment**")
            eq_cols = st.columns(len(equip_types))
            equipment = {t: col.number_input(t, 0, 5, 0, key=f"eq_{t}") for t, col in zip(equip_types, eq_cols)}
            st.markdown("**Volunteers**")
            vol_cols = st.columns(len(skills))
            volunteers = {s: col.number_input(s, 0, 10, 0, key=f"vol_{s}") for s, col in zip(skills, vol_cols)}
            a, b, c = st.columns(3)
            extra = a.number_input("Other costs (₹)", 0, 100000, 0, step=500)
            flex = b.slider("Can shift by (hours)", 0, 4, 1)
            ratio = c.slider("Minimum volunteers you'd accept", 0.0, 1.0, 1.0, 0.1)
            submitted = st.form_submit_button("Send request to the agents", type="primary")

        if submitted:
            new = dict(name=name.strip(), priority=priority, participants=int(participants), start=start, end=end,
                       venue_types=types, preferred_venue=None if pref == "—" else pref,
                       equipment={k: int(v) for k, v in equipment.items() if v},
                       volunteers={k: int(v) for k, v in volunteers.items() if v},
                       extra_cost=int(extra), flexible_hours=flex, min_volunteer_ratio=ratio)
            try:
                fest_model(st.session_state.my_events + [new], strategy)   # validate before keeping it
                st.session_state.my_events.append(new)
                st.rerun()
            except (ValueError, TypeError) as e:
                st.error(f"Invalid request: {e}")

        if st.session_state.my_events:
            last = st.session_state.my_events[-1]["name"]
            tick = len(st.session_state.my_events)
            if last in model.allocations:
                a = model.allocations[last]
                st.success(f"✓ **{last}** booked: {a['venue']} {fmt(a['start'], a['end'])}, ₹{a['cost']:,}"
                           + (f" — negotiated: {'; '.join(a['changes'])}" if a["changes"] else " — exactly as requested"))
            else:
                st.error(f"✗ **{last}** not booked — {model.rejected.get(last, 'see conversation')}")
            st.markdown(f"**How the five agents handled it** (step {tick})")
            conversation(model.log, tick)
            if st.button("Clear my requests"):
                st.session_state.my_events = []
                st.rerun()

# ------------------------------------------------------------------ review scenarios
else:
    name = st.sidebar.selectbox("Scenario", list(SCENARIOS))
    spec_text = st.sidebar.text_area("Scenario input (editable JSON)", json.dumps(SCENARIOS[name], indent=2),
                                     height=420, key=name)
    try:
        spec = json.loads(spec_text)
        model = make_model(spec, strategy).run()
        other = make_model(spec, "greedy" if strategy == "astar" else "astar").run()
    except (ValueError, TypeError, KeyError) as e:
        st.error(f"Invalid input: {e}")
        st.stop()

    m = model.metrics()
    spent = sum(a["cost"] for a in model.allocations.values())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Events scheduled", f"{len(model.allocations)} / {len(model.coordinator.requests)}")
    c2.metric("Overall score", m["score"], f"{m['score'] - other.metrics()['score']:+.3f} vs other strategy")
    c3.metric("Budget used", f"₹{spent:,}", f"₹{model.budget_agent.remaining:,} left", delta_color="off")
    c4.metric("Double bookings", m["C"])

    tab_alloc, tab_log, tab_cmp = st.tabs(["Final allocation", "Agent conversation", "A* vs Greedy"])
    with tab_alloc:
        allocation_table(model)
        if model.allocations:
            gantt = pd.DataFrame([{"Venue": a["venue"], "Event": a["event"], "start": a["start"], "end": a["end"],
                                   "Time": fmt(a["start"], a["end"])} for a in model.allocations.values()])
            base = alt.Chart(gantt).encode(
                y=alt.Y("Venue:N", title=None),
                x=alt.X("start:Q", title="Hour", scale=alt.Scale(domain=[FEST_START, FEST_END]),
                        axis=alt.Axis(tickCount=12)),
                x2="end:Q", tooltip=["Event", "Venue", "Time"])
            bars = base.mark_bar(color="#2a78d6", cornerRadius=4, height=22)
            labels = base.mark_text(align="left", dx=6, color="white").encode(text="Event:N")
            st.altair_chart((bars + labels).properties(height=60 + 34 * gantt["Venue"].nunique()), width="stretch")
    with tab_log:
        who = st.selectbox("Show messages involving", ["All"] + list(model.registry))
        conversation([(t, msg) for t, msg in model.log if who == "All" or who in (msg.sender, msg.receiver)])
    with tab_cmp:
        runs = {strategy: model, ("greedy" if strategy == "astar" else "astar"): other}
        st.dataframe(pd.DataFrame([{"Strategy": "A*" if k == "astar" else "Greedy", **r.metrics(),
                                    "Scheduled": len(r.allocations), "Rejected": ", ".join(r.rejected) or "—"}
                                   for k, r in sorted(runs.items())]), hide_index=True, width="stretch")
        st.caption("Score = 0.15·U + 0.30·S + 0.30·P + 0.25·F − 1.0·C − 1.0·B  "
                   "(U utilization, S scheduled, P priority satisfied, F Jain fairness, C conflicts, B budget overrun)")
