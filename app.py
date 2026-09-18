"""
DA'IRA — Circular Intelligence Digital Twin for Soudah
app.py — main Streamlit UI (operational command center)

Run with:  streamlit run app.py
"""

import io
import json
import random

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

from models import (
    get_state, reset_state, log_event, log_audit, snapshot_timeline, new_id, now_str,
)
from aerial_intelligence import analyze_image, CATEGORY_LABELS
from approval_workflow import validate_detection, decide_on_recommendation
from matching_engine import find_candidate_matches, create_match, compute_demand_view
from circular_router import (
    build_route, find_consolidation_candidates, apply_consolidation, apply_scenario,
)
from recommendation_engine import generate_recommendation_for_route
from carbon_cost_calculator import circular_value as calc_circular_value

# ----------------------------------------------------------------------------
# Page config + style
# ----------------------------------------------------------------------------

st.set_page_config(page_title="DA'IRA — Soudah Digital Twin", layout="wide", page_icon="🜲")

PRIMARY = "#1b3a34"
ACCENT = "#c9a24b"
BG = "#0e1a17"

st.markdown(f"""
<style>
    .stApp {{ background-color: #f6f5f1; }}
    .daira-header {{
        background: linear-gradient(120deg, {PRIMARY} 0%, #274c44 100%);
        padding: 22px 28px; border-radius: 10px; color: #f6f5f1; margin-bottom: 18px;
    }}
    .daira-header h1 {{ margin: 0; font-size: 28px; letter-spacing: 1px; }}
    .daira-header p {{ margin: 4px 0 0 0; opacity: 0.85; font-size: 14px; }}
    .kpi-box {{
        background: white; border: 1px solid #e2e0d8; border-radius: 8px;
        padding: 14px 16px; text-align: left;
    }}
    .kpi-label {{ font-size: 12px; color: #6b6b63; text-transform: uppercase; letter-spacing: 0.5px; }}
    .kpi-value {{ font-size: 24px; font-weight: 700; color: {PRIMARY}; }}
    .status-pill {{
        display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;
    }}
    .status-ACTIVE, .status-DISPATCHED, .status-MATCHED, .status-HUMAN_VALIDATED, .status-VALIDATED_WITH_HUMAN_REVIEW {{ background:#dcefe4; color:#1b6b3c; }}
    .status-WARNING, .status-REVIEW_REQUIRED, .status-PENDING_REVIEW, .status-PENDING_DECISION {{ background:#fbeecb; color:#8a6412; }}
    .status-BLOCKED, .status-REJECTED, .status-OFFLINE {{ background:#f7dede; color:#a12f2f; }}
    .status-DELAYED, .status-REROUTE_REQUIRED, .status-CONSOLIDATED {{ background:#e4e6f7; color:#3a3f9c; }}
    .status-IDLE, .status-UNKNOWN {{ background:#eaeae5; color:#5b5b55; }}
</style>
""", unsafe_allow_html=True)

state = get_state()

st.markdown("""
<div class="daira-header">
<h1>DA’IRA — دائرة</h1>
<p>Circular Intelligence Digital Twin for Soudah · Real World → Aerial Intelligence → AI Analysis → Human Validation → Digital Twin → Match → Optimize → Recommend → Decide → Audit</p>
</div>
""", unsafe_allow_html=True)

NAV_ITEMS = [
    "1 · Control Center", "2 · Aerial Intelligence", "3 · Digital Twin", "4 · Resource & Demand",
    "5 · Matching Engine", "6 · Fleet & Routes", "7 · Scenario Simulator", "8 · AI Recommendations",
    "9 · Decision Center", "10 · Audit Trail",
]

with st.sidebar:
    st.markdown("### Navigation")
    page = st.radio("Go to", NAV_ITEMS, label_visibility="collapsed")
    st.markdown("---")
    if st.button("▶ Run Guided Demonstration", use_container_width=True):
        st.session_state["run_demo"] = True
    if st.button("↺ Reset Digital Twin", use_container_width=True):
        reset_state()
        st.session_state.pop("run_demo", None)
        st.rerun()
    st.caption("Prototype for the Aramco Consulting Championship. "
               "AI screening is heuristic and explanatory, not a certified "
               "engineering or agricultural measurement system.")


def status_pill(text):
    cls = f"status-{str(text).upper().replace(' ', '_')}"
    return f'<span class="status-pill {cls}">{text}</span>'


def node_options(node_type=None):
    return {nid: n["name"] for nid, n in state["nodes"].items() if node_type is None or n["type"] == node_type}


# ----------------------------------------------------------------------------
# Guided demonstration (Section 27)
# ----------------------------------------------------------------------------

def synthetic_drone_image(kind: str) -> Image.Image:
    """Generate a synthetic drone-style image so the demo runs with no external files."""
    rng = np.random.default_rng(7 if kind == "RESOURCE" else 3)
    if kind == "RESOURCE":
        base = np.zeros((160, 160, 3))
        base[:, :, 1] = 0.55 + rng.normal(0, 0.05, (160, 160))
        base[:, :, 0] = 0.25 + rng.normal(0, 0.05, (160, 160))
        base[:, :, 2] = 0.15
    else:
        base = np.zeros((160, 160, 3))
        base[:, :, 0] = 0.5 + rng.normal(0, 0.05, (160, 160))
        base[:, :, 1] = 0.48 + rng.normal(0, 0.05, (160, 160))
        base[:, :, 2] = 0.45 + rng.normal(0, 0.05, (160, 160))
        base[100:120, :, :] = 0.12  # dark obstruction band
    base = np.clip(base, 0, 1)
    return Image.fromarray((base * 255).astype("uint8"))


def run_guided_demo():
    log = st.container()
    with log:
        st.info("Running guided demonstration end-to-end on FARM-01 → HOTEL-01 …")

        img = synthetic_drone_image("RESOURCE")
        detection = analyze_image(img, "RESOURCE", "FARM-01")
        st.write(f"**1. Aerial observation received.** AI Screening Signal: "
                 f"{detection['category_label']} — confidence {detection['confidence']}%, "
                 f"estimated {detection['estimated_quantity_kg']} kg.")

        resource_id = validate_detection(detection["detection_id"], "APPROVE",
                                          validated_qty=50, resource_type="FRESH_PRODUCE",
                                          actor="Operations Manager (Demo)",
                                          notes="Guided demo validation")
        st.write(f"**2. Human validation completed.** Validated quantity: 50 kg → resource `{resource_id}` created.")
        snapshot_timeline("AFTER AERIAL OBSERVATION", "Farm resource confirmed via aerial intelligence")

        candidates = find_candidate_matches(resource_id)
        if candidates:
            top = candidates[0]
            match_id = create_match(resource_id, top["demand_node"], top["matched_quantity"],
                                     top["score"], top["breakdown"], top["distance_km"],
                                     actor="Matching Engine (Demo)")
            st.write(f"**3. Matching engine generated candidate.** {top['matched_quantity']} kg → "
                     f"{top['demand_name']}, match score {top['score']}.")
            snapshot_timeline("AFTER MATCHING", f"{top['matched_quantity']} kg matched to {top['demand_name']}")

            route = build_route(match_id, actor="Fleet Engine (Demo)")
            st.write(f"**4. Route optimization completed.** Vehicle `{route.get('vehicle_id')}`, "
                     f"utilization {route.get('utilization_pct')}%.")
            snapshot_timeline("AFTER ROUTE ANALYSIS", f"Vehicle utilization {route.get('utilization_pct')}%")

            if route["status"] not in ("BLOCKED",):
                consolidation = find_consolidation_candidates(route["route_id"])
                st.write(f"**5. Consolidation check triggered.** "
                         f"{'Candidate found.' if consolidation else 'No compatible route found — proceeding standalone.'}")

            rec = generate_recommendation_for_route(route["route_id"])
            st.write(f"**6. AI recommendation generated:** `{rec['action']}` — {rec['reason']}")

            st.success("Guided demonstration complete. Open **Decision Center** to approve/modify/reject, "
                       "and **Audit Trail** to inspect the full lineage.")
        else:
            st.warning("No compatible demand candidate found for the demo resource.")


if st.session_state.get("run_demo"):
    run_guided_demo()
    st.session_state["run_demo"] = False
    st.markdown("---")


# ----------------------------------------------------------------------------
# 1. CONTROL CENTER
# ----------------------------------------------------------------------------

if page == NAV_ITEMS[0]:
    total_resources = sum(r["quantity"] for r in state["resources"].values())
    total_demand = sum(n["current_demand_kg"] for n in state["nodes"].values() if n["type"] == "HOTEL")
    total_matched = sum(m["matched_quantity"] for m in state["matches"].values() if m["status"] != "REJECTED")
    unmatched = max(0, total_resources - total_matched)
    active_routes = [r for r in state["routes"].values() if r["status"] not in ("BLOCKED",)]
    fleet_util = round(np.mean([v["utilization_pct"] for v in state["vehicles"].values()]), 1) if state["vehicles"] else 0
    total_cost = sum(r.get("cost", 0) for r in state["routes"].values())
    total_co2 = sum(r.get("co2_kg", 0) for r in state["routes"].values())
    total_circular_value = sum(r.get("circular_value", {}).get("circular_value", 0) for r in state["routes"].values())
    pending_decisions = sum(1 for r in state["recommendations"].values() if not r.get("human_decision"))
    risks = sum(1 for n in state["nodes"].values() if n.get("risk_level") == "HIGH" or n.get("status") == "REVIEW_REQUIRED")

    cols = st.columns(5)
    kpis = [
        ("Active Nodes", len(state["nodes"])),
        ("Total Available Resources (kg)", round(total_resources, 1)),
        ("Total Demand (kg)", round(total_demand, 1)),
        ("Matched Quantity (kg)", round(total_matched, 1)),
        ("Unmatched Quantity (kg)", round(unmatched, 1)),
    ]
    for c, (label, val) in zip(cols, kpis):
        c.markdown(f'<div class="kpi-box"><div class="kpi-label">{label}</div><div class="kpi-value">{val}</div></div>', unsafe_allow_html=True)

    cols2 = st.columns(5)
    kpis2 = [
        ("Fleet Utilization (%)", fleet_util),
        ("Transport Cost (SAR)", round(total_cost, 2)),
        ("CO₂ (kg)", round(total_co2, 2)),
        ("Circular Value (SAR)", round(total_circular_value, 2)),
        ("Pending Decisions", pending_decisions),
    ]
    for c, (label, val) in zip(cols2, kpis2):
        c.markdown(f'<div class="kpi-box"><div class="kpi-label">{label}</div><div class="kpi-value">{val}</div></div>', unsafe_allow_html=True)

    st.markdown("### Digital Twin Status")
    rows = []
    for nid, n in state["nodes"].items():
        rows.append({"ID": nid, "Type": n["type"], "Name": n["name"], "Status": n.get("status", n.get("service_status", "—"))})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### Live Event Feed")
    if state["events"]:
        for e in reversed(state["events"][-12:]):
            st.markdown(f"`{e['time']}` **{e['type']}** — {e['signal']} "
                        f"{status_pill(e['status']) if e['status'] else ''}", unsafe_allow_html=True)
    else:
        st.caption("No events yet. Run the guided demonstration or use Aerial Intelligence to begin.")

# ----------------------------------------------------------------------------
# 2. AERIAL INTELLIGENCE
# ----------------------------------------------------------------------------

elif page == NAV_ITEMS[1]:
    st.subheader("Aerial Intelligence — AI Screening Layer")
    st.caption("Drone imagery is screened with a heuristic computer-vision pass. "
               "This produces an *AI Screening Signal* only — every detection requires human validation "
               "before it can change the Digital Twin.")

    c1, c2 = st.columns([1, 1])
    with c1:
        mode = st.radio("Screening mode", ["RESOURCE", "INFRASTRUCTURE"], horizontal=True)
        target_pool = "FARM" if mode == "RESOURCE" else "ROAD"
        target_entity = st.selectbox("Target entity", options=list(node_options(target_pool).keys()),
                                      format_func=lambda k: node_options(target_pool)[k])
        uploaded = st.file_uploader("Upload drone image (jpg/png)", type=["png", "jpg", "jpeg"])
        use_sample = st.checkbox("Use synthetic sample image instead", value=uploaded is None)

        if st.button("Run AI Screening", type="primary"):
            if uploaded is not None and not use_sample:
                img = Image.open(uploaded)
            else:
                img = synthetic_drone_image(mode)
            detection = analyze_image(img, mode, target_entity)
            st.session_state["last_detection_id"] = detection["detection_id"]
            st.session_state["last_image"] = img

    with c2:
        if st.session_state.get("last_image") is not None:
            st.image(st.session_state["last_image"], caption="Screened image (preview)", use_container_width=True)

    det_id = st.session_state.get("last_detection_id")
    if det_id and det_id in state["aerial_detections"]:
        d = state["aerial_detections"][det_id]
        st.markdown("#### Detection Result")
        st.markdown(f"**Category:** AI Screening Signal — {d['category_label']}  \n"
                    f"**Confidence:** {d['confidence']}%  \n"
                    f"**Estimated quantity:** {d['estimated_quantity_kg']} kg" if d['estimated_quantity_kg'] is not None else
                    f"**Category:** AI Screening Signal — {d['category_label']}  \n**Confidence:** {d['confidence']}%")
        st.markdown(f"Status: {status_pill(d['validation_status'])}", unsafe_allow_html=True)

        if d["validation_status"] == "PENDING_REVIEW":
            st.markdown("##### Human Validation")
            colA, colB, colC = st.columns(3)
            with colA:
                if d["mode"] == "RESOURCE":
                    qty = st.number_input("Validated quantity (kg)", min_value=0.0,
                                           value=float(d["estimated_quantity_kg"] or 0), step=1.0)
                    rtype = st.selectbox("Resource type", ["FRESH_PRODUCE", "GRAIN", "DAIRY"])
                else:
                    qty, rtype = None, None
                notes = st.text_input("Notes", key="val_notes")
            with colB:
                if st.button("✅ Approve"):
                    result = validate_detection(det_id, "APPROVE", validated_qty=qty, resource_type=rtype, notes=notes)
                    st.success(f"Validated → {result}")
                    st.rerun()
            with colC:
                if st.button("❌ Reject"):
                    validate_detection(det_id, "REJECT", notes=notes)
                    st.warning("Detection rejected.")
                    st.rerun()
                if st.button("🔁 Request Re-analysis"):
                    validate_detection(det_id, "REANALYZE")
                    st.info("Marked for re-analysis.")
                    st.rerun()

    st.markdown("#### All Pending / Recent Detections")
    if state["aerial_detections"]:
        df = pd.DataFrame([{
            "Detection": k, "Entity": v["target_entity"], "Category": v["category_label"],
            "Confidence %": v["confidence"], "Status": v["validation_status"],
        } for k, v in state["aerial_detections"].items()])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("No detections yet.")

# ----------------------------------------------------------------------------
# 3. DIGITAL TWIN (network visualization)
# ----------------------------------------------------------------------------

elif page == NAV_ITEMS[2]:
    st.subheader("Digital Twin — Network View")

    color_map = {
        "ACTIVE": "#2f9e5c", "WARNING": "#e0a92e", "REVIEW_REQUIRED": "#e0a92e",
        "DISPATCHED": "#2f6fa8", "DELAYED": "#8a6fd6", "BLOCKED": "#c0392b",
        "OFFLINE": "#7a7a7a", "IDLE": "#b0ada0", "UNKNOWN": "#b0ada0",
    }

    fig = go.Figure()
    pos = {nid: n["location"] for nid, n in state["nodes"].items() if "location" in n}

    for road in state["nodes"].values():
        if road["type"] != "ROAD":
            continue
        a, b = road["connects"]
        if a in pos and b in pos:
            line_color = "#c0392b" if road["status"] in ("BLOCKED", "REVIEW_REQUIRED") else "#9c9484"
            fig.add_trace(go.Scatter(
                x=[pos[a][1], pos[b][1]], y=[pos[a][0], pos[b][0]],
                mode="lines", line=dict(color=line_color, width=3, dash="solid" if road["status"] == "ACTIVE" else "dash"),
                hoverinfo="text", text=f"{road['name']} — {road['status']}", showlegend=False,
            ))

    for match in state["matches"].values():
        if match["status"] == "REJECTED":
            continue
        a, b = match["source_node"], match["demand_node"]
        if a in pos and b in pos:
            fig.add_trace(go.Scatter(
                x=[pos[a][1], pos[b][1]], y=[pos[a][0], pos[b][0]],
                mode="lines", line=dict(color="#c9a24b", width=2, dash="dot"),
                hoverinfo="text", text=f"Resource flow {match['matched_quantity']} kg", showlegend=False,
            ))

    shape_map = {"HUB": "square", "FARM": "circle", "HOTEL": "diamond"}
    for nid, n in state["nodes"].items():
        if n["type"] == "ROAD":
            continue
        status = n.get("status", n.get("service_status", "UNKNOWN"))
        fig.add_trace(go.Scatter(
            x=[n["location"][1]], y=[n["location"][0]], mode="markers+text",
            marker=dict(size=22, color=color_map.get(status, "#b0ada0"), symbol=shape_map.get(n["type"], "circle"),
                        line=dict(width=1, color="white")),
            text=[nid], textposition="bottom center",
            hovertext=f"{n['name']} ({n['type']}) — {status}", hoverinfo="text", showlegend=False,
        ))

    fig.update_layout(height=520, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis=dict(showgrid=False, zeroline=False, visible=False),
                       yaxis=dict(showgrid=False, zeroline=False, visible=False),
                       plot_bgcolor="#f6f5f1", paper_bgcolor="#f6f5f1")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Squares = Hub · Circles = Farms · Diamonds = Hotels · Gold dotted lines = active resource flow · Red dashed = disrupted road")

    st.markdown("#### Entity Inspector")
    entity_id = st.selectbox("Select entity", list(state["nodes"].keys()) + list(state["vehicles"].keys()))
    entity = state["nodes"].get(entity_id) or state["vehicles"].get(entity_id)
    st.json(entity)

# ----------------------------------------------------------------------------
# 4. RESOURCE & DEMAND
# ----------------------------------------------------------------------------

elif page == NAV_ITEMS[3]:
    st.subheader("Resource & Demand")

    st.markdown("#### Resources (validated)")
    if state["resources"]:
        st.dataframe(pd.DataFrame(state["resources"].values()), use_container_width=True, hide_index=True)
    else:
        st.caption("No validated resources yet — use Aerial Intelligence to create one.")

    st.markdown("#### Demand (hotels / hospitality nodes)")
    rows = []
    for nid, n in state["nodes"].items():
        if n["type"] != "HOTEL":
            continue
        dv = compute_demand_view(nid)
        rows.append({
            "Node": nid, "Name": n["name"], "Demand (kg)": dv["demand_total"],
            "Matched (kg)": dv["matched"], "Remaining (kg)": dv["remaining"],
            "Coverage %": dv["coverage_pct"], "Supply Status": n["supply_status"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# 5. MATCHING ENGINE
# ----------------------------------------------------------------------------

elif page == NAV_ITEMS[4]:
    st.subheader("Matching Engine — Resource → Demand")

    available = {rid: r for rid, r in state["resources"].items() if r.get("available_for_matching")}
    if not available:
        st.info("No resources available for matching yet. Validate an aerial detection first.")
    else:
        resource_id = st.selectbox("Resource", list(available.keys()),
                                    format_func=lambda r: f"{r} — {available[r]['quantity']} kg {available[r]['resource_type']} (conf {available[r]['confidence']}%)")
        if st.button("Find Candidate Matches"):
            st.session_state["match_candidates"] = find_candidate_matches(resource_id)
            st.session_state["match_resource"] = resource_id

        candidates = st.session_state.get("match_candidates")
        if candidates and st.session_state.get("match_resource") == resource_id:
            for c in candidates:
                with st.container(border=True):
                    st.markdown(f"**{c['demand_name']}** ({c['demand_node']}) — Match Score **{c['score']}**")
                    st.write(f"Proposed match: {c['matched_quantity']} kg · distance {c['distance_km']} km · "
                             f"cold-chain OK: {c['cold_chain_ok']}")
                    bcols = st.columns(5)
                    for bc, (k, v) in zip(bcols, c["breakdown"].items()):
                        bc.metric(k.replace("_contribution", "").replace("_", " ").title(), v)
                    if st.button(f"Create Match → {c['demand_node']}", key=f"match_{c['demand_node']}"):
                        try:
                            match_id = create_match(resource_id, c["demand_node"], c["matched_quantity"],
                                                      c["score"], c["breakdown"], c["distance_km"])
                            st.success(f"Match created: {match_id}")
                            st.session_state.pop("match_candidates", None)
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
            if not candidates:
                st.warning("No compatible demand found for this resource (type/cold-chain mismatch or demand already covered).")

    st.markdown("#### Existing Matches")
    if state["matches"]:
        st.dataframe(pd.DataFrame(state["matches"].values()).drop(columns=["breakdown"], errors="ignore"),
                     use_container_width=True, hide_index=True)
    else:
        st.caption("No matches yet.")

# ----------------------------------------------------------------------------
# 6. FLEET & ROUTES
# ----------------------------------------------------------------------------

elif page == NAV_ITEMS[5]:
    st.subheader("Fleet & Routes")

    unrouted = [mid for mid, m in state["matches"].items()
                if m["status"] != "REJECTED" and not any(mid in r["match_ids"] for r in state["routes"].values())]
    if unrouted:
        mid = st.selectbox("Match awaiting a route", unrouted)
        if st.button("Build Route"):
            route = build_route(mid)
            st.rerun()
    else:
        st.caption("No unrouted matches. Create a match in the Matching Engine first.")

    st.markdown("#### Routes")
    for rid, r in state["routes"].items():
        with st.container(border=True):
            st.markdown(f"**{rid}** {status_pill(r['status'])}", unsafe_allow_html=True)
            if r["status"] == "BLOCKED":
                st.write(r["reason"])
                continue
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Load (kg)", r["quantity_kg"])
            c2.metric("Utilization %", r["utilization_pct"])
            c3.metric("Cost (SAR)", r["cost"])
            c4.metric("CO₂ (kg)", r["co2_kg"])
            st.caption(f"{r['source_node']} → {r['demand_node']} via {r['vehicle_id']} · "
                       f"{r['distance_km']} km · road: {r['road_status']}")
            cv = r["circular_value"]
            st.write(f"Circular value: **{cv['circular_value']} SAR** "
                     f"(local sourcing {cv['local_sourcing_value']} + avoided waste {cv['avoided_waste_value']} − transport {cv['transport_cost']})")

            if r.get("low_utilization") and not r.get("consolidated"):
                st.warning(f"LOW UTILIZATION — below {20}% threshold. Consolidation recommended.")
                cands = find_consolidation_candidates(rid)
                if cands:
                    for cand in cands:
                        st.write(f"↳ Combine with `{cand['other_route_id']}`: "
                                 f"{cand['current_load_kg']} + {cand['other_load_kg']} kg → "
                                 f"{cand['combined_load_kg']} kg, utilization {cand['current_utilization_pct']}% → {cand['projected_utilization_pct']}%")
                        if st.button(f"Consolidate {rid} with {cand['other_route_id']}", key=f"cons_{rid}_{cand['other_route_id']}"):
                            apply_consolidation(rid, cand["other_route_id"])
                            st.rerun()
                else:
                    st.caption("No compatible route currently exists to consolidate with.")

    st.markdown("#### Vehicles")
    st.dataframe(pd.DataFrame(state["vehicles"].values()), use_container_width=True, hide_index=True)

# ----------------------------------------------------------------------------
# 7. SCENARIO SIMULATOR
# ----------------------------------------------------------------------------

elif page == NAV_ITEMS[6]:
    st.subheader("Scenario Simulator — What-If")
    scenario = st.selectbox("Scenario", [
        "ROAD_DISRUPTION", "VEHICLE_UNAVAILABLE", "RESOURCE_REDUCTION", "DEMAND_INCREASE",
    ])

    if scenario == "ROAD_DISRUPTION":
        road_id = st.selectbox("Road", list(node_options("ROAD").keys()), format_func=lambda k: node_options("ROAD")[k])
        if st.button("Apply: What if road access is disrupted?"):
            apply_scenario("ROAD_DISRUPTION", {"road_id": road_id})
            snapshot_timeline("SCENARIO: ROAD DISRUPTION", f"{road_id} blocked")
            st.rerun()

    elif scenario == "VEHICLE_UNAVAILABLE":
        vehicle_id = st.selectbox("Vehicle", list(state["vehicles"].keys()))
        if st.button("Apply: What if this vehicle becomes unavailable?"):
            apply_scenario("VEHICLE_UNAVAILABLE", {"vehicle_id": vehicle_id})
            snapshot_timeline("SCENARIO: VEHICLE UNAVAILABLE", f"{vehicle_id} offline")
            st.rerun()

    elif scenario == "RESOURCE_REDUCTION":
        farm_id = st.selectbox("Farm", list(node_options("FARM").keys()), format_func=lambda k: node_options("FARM")[k])
        factor = st.slider("Remaining fraction of resource", 0.0, 1.0, 0.5)
        if st.button("Apply: What if available farm resource decreases?"):
            apply_scenario("RESOURCE_REDUCTION", {"farm_id": farm_id, "factor": factor})
            snapshot_timeline("SCENARIO: RESOURCE REDUCTION", f"{farm_id} reduced to {factor*100:.0f}%")
            st.rerun()

    elif scenario == "DEMAND_INCREASE":
        hotel_id = st.selectbox("Hotel", list(node_options("HOTEL").keys()), format_func=lambda k: node_options("HOTEL")[k])
        delta = st.number_input("Demand increase (kg)", min_value=0, value=100, step=10)
        if st.button("Apply: What if hotel demand increases?"):
            apply_scenario("DEMAND_INCREASE", {"hotel_id": hotel_id, "delta_kg": delta})
            snapshot_timeline("SCENARIO: DEMAND INCREASE", f"{hotel_id} +{delta} kg")
            st.rerun()

    st.markdown("#### Timeline — Digital Twin state over time")
    if state["timeline_snapshots"]:
        for snap in state["timeline_snapshots"]:
            with st.expander(f"{snap['time']} — {snap['label']}"):
                st.write(snap["note"])
                st.json({"farms": snap["farms"], "hotels": snap["hotels"], "vehicle_utilization": snap["vehicle_utilization"]})
    else:
        st.caption("No snapshots yet — snapshots are captured automatically as the demo/scenarios run.")

# ----------------------------------------------------------------------------
# 8. AI RECOMMENDATIONS
# ----------------------------------------------------------------------------

elif page == NAV_ITEMS[7]:
    st.subheader("AI Recommendations")

    routable = [rid for rid in state["routes"].keys()
                if not any(rec["route_id"] == rid for rec in state["recommendations"].values())]
    if routable:
        rid = st.selectbox("Route needing a recommendation", routable)
        if st.button("Generate Recommendation"):
            generate_recommendation_for_route(rid)
            st.rerun()
    else:
        st.caption("All current routes already have a recommendation, or no routes exist yet.")

    for rec_id, rec in state["recommendations"].items():
        with st.container(border=True):
            st.markdown(f"**{rec_id}** — `{rec['action']}` {status_pill(rec['human_decision'] or 'PENDING_DECISION')}", unsafe_allow_html=True)
            st.write(rec["reason"])
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Cost impact (SAR)", rec["cost_impact"])
            c2.metric("CO₂ impact (kg)", rec["co2_impact"])
            c3.metric("Circular value (SAR)", rec["circular_value"])
            c4.metric("Confidence", f"{round(rec['confidence']*100)}%")
            if rec["risks"]:
                st.caption("Risks: " + ", ".join(rec["risks"]))

# ----------------------------------------------------------------------------
# 9. DECISION CENTER
# ----------------------------------------------------------------------------

elif page == NAV_ITEMS[8]:
    st.subheader("Decision Center — Human-in-the-Loop")
    pending = {rid: r for rid, r in state["recommendations"].items() if not r.get("human_decision")}
    if not pending:
        st.caption("No pending recommendations.")
    for rec_id, rec in pending.items():
        with st.container(border=True):
            st.markdown(f"**{rec_id}** — recommended action: `{rec['action']}`")
            st.write(rec["reason"])
            reason_input = st.text_input("Decision reason / notes", key=f"reason_{rec_id}")
            c1, c2, c3 = st.columns(3)
            if c1.button("✅ Approve", key=f"approve_{rec_id}"):
                decide_on_recommendation(rec_id, "APPROVE", reason=reason_input)
                st.rerun()
            if c2.button("✏️ Modify", key=f"modify_{rec_id}"):
                decide_on_recommendation(rec_id, "MODIFY", reason=reason_input or "Operator requested modification")
                st.rerun()
            if c3.button("❌ Reject", key=f"reject_{rec_id}"):
                decide_on_recommendation(rec_id, "REJECT", reason=reason_input)
                st.rerun()

    st.markdown("#### Decision Log")
    if state["decisions"]:
        st.dataframe(pd.DataFrame(state["decisions"]), use_container_width=True, hide_index=True)
    else:
        st.caption("No decisions recorded yet.")

# ----------------------------------------------------------------------------
# 10. AUDIT TRAIL
# ----------------------------------------------------------------------------

elif page == NAV_ITEMS[9]:
    st.subheader("Audit Trail")

    st.markdown("#### Immutable Audit Log")
    if state["audit_trail"]:
        df = pd.DataFrame([{
            "Time": a["timestamp"], "Event": a["event_type"], "Actor": a["actor"],
            "Entity": a["entity"], "Reason": a["reason"],
        } for a in state["audit_trail"]])
        st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander("Inspect full before/after state for an audit event"):
            idx = st.number_input("Row index", min_value=0, max_value=len(state["audit_trail"]) - 1, value=0)
            st.json(state["audit_trail"][idx])
    else:
        st.caption("No audit events yet.")

    st.markdown("#### Full Event Feed")
    if state["events"]:
        st.dataframe(pd.DataFrame(state["events"]), use_container_width=True, hide_index=True)

    st.markdown("#### Export")
    export = {
        "nodes": state["nodes"], "vehicles": state["vehicles"], "resources": state["resources"],
        "matches": state["matches"], "routes": state["routes"], "recommendations": state["recommendations"],
        "decisions": state["decisions"], "audit_trail": state["audit_trail"], "events": state["events"],
    }
    st.download_button("⬇ Export Digital Twin State (JSON)",
                       data=json.dumps(export, indent=2, default=str),
                       file_name="daira_digital_twin_state.json", mime="application/json")
