"""
recommendation_engine.py

Generates an explainable recommendation from the ACTUAL current
Digital Twin state (never fabricated). AI does not auto-execute —
every recommendation waits in the Decision Center for a human
APPROVE / MODIFY / REJECT.
"""

from __future__ import annotations
from models import get_state, new_id, now_str, log_event
from circular_router import LOW_UTILIZATION_THRESHOLD_PCT, find_consolidation_candidates


def generate_recommendation_for_route(route_id: str) -> dict:
    state = get_state()
    route = state["routes"][route_id]
    rec_id = new_id("REC")

    if route["status"] == "BLOCKED":
        action, reason, confidence = "HOLD FOR REVIEW", "No suitable vehicle is currently available for this route.", 0.9
    elif route["status"] == "REROUTE_REQUIRED":
        action, reason, confidence = "REROUTE", f"Road on this corridor is {route['road_status']}; an alternative path must be evaluated before dispatch.", 0.75
    elif route.get("low_utilization") and find_consolidation_candidates(route_id):
        action = "CONSOLIDATE"
        reason = (f"Validated resource quantity yields only {route['utilization_pct']}% vehicle utilization "
                   f"(below the {LOW_UTILIZATION_THRESHOLD_PCT}% threshold). A compatible route exists to combine with.")
        confidence = 0.8
    elif route.get("low_utilization"):
        action = "WAIT FOR MORE DATA"
        reason = (f"Utilization is only {route['utilization_pct']}%, and no compatible consolidation route "
                   "currently exists. No operational urgency identified to justify a dedicated trip.")
        confidence = 0.6
    else:
        action = "DISPATCH"
        reason = f"Utilization is {route['utilization_pct']}% with an active road and available vehicle — dispatch is operationally justified."
        confidence = 0.85

    rec = {
        "rec_id": rec_id,
        "route_id": route_id,
        "action": action,
        "reason": reason,
        "affected_entities": [route.get("source_node"), route.get("demand_node"), route.get("vehicle_id")],
        "vehicle_id": route.get("vehicle_id"),
        "cost_impact": route.get("cost"),
        "co2_impact": route.get("co2_kg"),
        "circular_value": route.get("circular_value", {}).get("circular_value") if route.get("circular_value") else None,
        "confidence": confidence,
        "risks": [] if action == "DISPATCH" else ["Low utilization" if route.get("low_utilization") else "Operational uncertainty"],
        "requires_human_decision": True,
        "human_decision": None,
        "timestamp": now_str(),
    }
    state["recommendations"][rec_id] = rec
    log_event("RECOMMENDATION", rec_id, f"AI recommends: {action}", confidence=round(confidence * 100, 1), status="PENDING_DECISION")
    return rec
