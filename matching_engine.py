"""
matching_engine.py

Connects RESOURCE -> DEMAND. Enforces the data-lineage rules:
  RULE 1: validated quantity must equal or exceed matched quantity
  RULE 2: matched quantity cannot exceed receiver demand
  RULE 6: recommendations must reference real current state
Every match score is fully decomposed — no unexplained AI numbers.
"""

from __future__ import annotations
import math

from models import get_state, new_id, now_str, log_event, log_audit

# Haversine-free flat approximation is fine at this scale (few km across Soudah)
def _distance_km(loc_a, loc_b):
    lat1, lon1 = loc_a
    lat2, lon2 = loc_b
    # rough km/degree at ~18N
    dlat = (lat2 - lat1) * 111.0
    dlon = (lon2 - lon1) * 105.0
    return round(math.hypot(dlat, dlon), 2)


def compute_demand_view(entity_id: str) -> dict:
    state = get_state()
    node = state["nodes"][entity_id]
    matched_total = sum(
        m["matched_quantity"] for m in state["matches"].values()
        if m["demand_node"] == entity_id and m["status"] != "REJECTED"
    )
    demand = node["current_demand_kg"]
    return {
        "demand_total": demand,
        "matched": matched_total,
        "remaining": max(0, demand - matched_total),
        "coverage_pct": round(min(100, (matched_total / demand) * 100), 1) if demand else 0.0,
    }


def find_candidate_matches(resource_id: str) -> list[dict]:
    """Score every hotel/demand node as a candidate for this resource."""
    state = get_state()
    resource = state["resources"][resource_id]
    farm = state["nodes"][resource["source_node"]]
    candidates = []

    for node_id, node in state["nodes"].items():
        if node["type"] != "HOTEL":
            continue
        if node.get("demand_type") != resource["resource_type"]:
            continue

        demand_view = compute_demand_view(node_id)
        if demand_view["remaining"] <= 0:
            continue

        cold_ok = (not resource.get("cold_chain_required")) or node.get("cold_chain_required")
        dist = _distance_km(farm["location"], node["location"])

        confidence_score = resource["confidence"] / 100.0
        coverage_needed = min(resource["quantity"], demand_view["remaining"])
        demand_coverage_score = coverage_needed / demand_view["demand_total"] if demand_view["demand_total"] else 0
        compatibility_score = 1.0 if cold_ok else 0.3
        distance_score = max(0.0, 1 - (dist / 25.0))  # 25km treated as far for this micro-region
        urgency_score = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.3}.get(node.get("shortage_risk", "LOW"), 0.3)

        weights = {"confidence": 0.25, "coverage": 0.25, "compatibility": 0.2, "distance": 0.15, "urgency": 0.15}
        score = (
            confidence_score * weights["confidence"]
            + demand_coverage_score * weights["coverage"]
            + compatibility_score * weights["compatibility"]
            + distance_score * weights["distance"]
            + urgency_score * weights["urgency"]
        )

        candidates.append({
            "demand_node": node_id,
            "demand_name": node["name"],
            "distance_km": dist,
            "matched_quantity": round(coverage_needed, 1),
            "score": round(score, 3),
            "breakdown": {
                "confidence_contribution": round(confidence_score * weights["confidence"], 3),
                "demand_coverage_contribution": round(demand_coverage_score * weights["coverage"], 3),
                "compatibility_contribution": round(compatibility_score * weights["compatibility"], 3),
                "distance_contribution": round(distance_score * weights["distance"], 3),
                "urgency_contribution": round(urgency_score * weights["urgency"], 3),
            },
            "cold_chain_ok": cold_ok,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def create_match(resource_id: str, demand_node: str, matched_quantity: float, score: float,
                  breakdown: dict, distance_km: float, actor="Matching Engine") -> str:
    state = get_state()
    resource = state["resources"][resource_id]

    # RULE 1: validated resource quantity must equal or exceed matched quantity
    if matched_quantity > resource["quantity"]:
        raise ValueError("RULE 1 VIOLATION: matched quantity exceeds validated resource quantity")

    # RULE 2: matched quantity cannot exceed receiver demand
    demand_view = compute_demand_view(demand_node)
    if matched_quantity > demand_view["remaining"] + 1e-6:
        raise ValueError("RULE 2 VIOLATION: matched quantity exceeds remaining receiver demand")

    match_id = new_id("MATCH")
    match = {
        "match_id": match_id,
        "resource_id": resource_id,
        "source_node": resource["source_node"],
        "demand_node": demand_node,
        "matched_quantity": matched_quantity,
        "unit": "kg",
        "score": score,
        "breakdown": breakdown,
        "distance_km": distance_km,
        "status": "MATCHED",
        "timestamp": now_str(),
    }
    state["matches"][match_id] = match

    hotel = state["nodes"][demand_node]
    dv = compute_demand_view(demand_node)
    hotel["supply_status"] = "COVERED" if dv["remaining"] == 0 else "PARTIAL" if dv["matched"] > 0 else "SHORTAGE"

    log_event("MATCHING", match_id, f"{matched_quantity} kg matched: {resource['source_node']} -> {demand_node}",
               confidence=resource["confidence"], status="MATCHED")
    log_audit("MATCH_CREATED", actor, match_id, None, match, f"Matched {matched_quantity} kg to {demand_node}")
    return match_id
