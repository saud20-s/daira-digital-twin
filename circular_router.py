"""
circular_router.py

Fleet selection, route construction, utilization/consolidation
analysis, and route re-optimization under changed scenarios
(road disruption, vehicle breakdown, demand/resource changes).
"""

from __future__ import annotations
import copy

from models import get_state, new_id, now_str, log_event, log_audit
from carbon_cost_calculator import transport_cost, transport_co2, utilization_pct, circular_value

LOW_UTILIZATION_THRESHOLD_PCT = 20.0


def road_status_between(source_node: str, demand_node: str) -> dict | None:
    """Return the road entity connecting two nodes, if modeled, else None."""
    state = get_state()
    for road in state["nodes"].values():
        if road["type"] != "ROAD":
            continue
        if set(road["connects"]) == {source_node, demand_node}:
            return road
    return None


def pick_vehicle(load_kg: float, cold_chain_required: bool) -> dict | None:
    state = get_state()
    candidates = [
        v for v in state["vehicles"].values()
        if v["availability"] == "AVAILABLE"
        and v["capacity_kg"] >= load_kg
        and (not cold_chain_required or v["cold_chain"])
    ]
    if not candidates:
        return None
    # smallest sufficient vehicle -> best baseline utilization
    candidates.sort(key=lambda v: v["capacity_kg"])
    return candidates[0]


def build_route(match_id: str, actor="Fleet Engine") -> dict:
    state = get_state()
    match = state["matches"][match_id]
    resource = state["resources"][match["resource_id"]]

    vehicle = pick_vehicle(match["matched_quantity"], resource.get("cold_chain_required", False))
    route_id = new_id("ROUTE")

    if vehicle is None:
        route = {
            "route_id": route_id, "match_ids": [match_id], "status": "BLOCKED",
            "reason": "No available vehicle meets capacity/cold-chain requirement",
            "vehicle_id": None, "quantity_kg": match["matched_quantity"],
        }
        state["routes"][route_id] = route
        log_event("ROUTE", route_id, "Route blocked — no suitable vehicle available", status="BLOCKED")
        return route

    road = road_status_between(match["source_node"], match["demand_node"])
    road_status = road["status"] if road else "UNKNOWN"
    distance_km = match["distance_km"]

    load = match["matched_quantity"]
    util = utilization_pct(load, vehicle["capacity_kg"])
    cost = transport_cost(distance_km, vehicle)
    co2 = transport_co2(distance_km, vehicle)
    cvalue = circular_value(load, distance_km, vehicle)

    status = "ACTIVE"
    if road_status in ("REVIEW_REQUIRED", "BLOCKED"):
        status = "REROUTE_REQUIRED"

    route = {
        "route_id": route_id,
        "match_ids": [match_id],
        "vehicle_id": vehicle["id"],
        "source_node": match["source_node"],
        "demand_node": match["demand_node"],
        "quantity_kg": load,
        "distance_km": distance_km,
        "utilization_pct": util,
        "low_utilization": util < LOW_UTILIZATION_THRESHOLD_PCT,
        "road_status": road_status,
        "cost": cost,
        "co2_kg": co2,
        "circular_value": cvalue,
        "status": status,
        "consolidated": False,
        "timestamp": now_str(),
    }
    state["routes"][route_id] = route

    vehicle["current_load_kg"] = load
    vehicle["utilization_pct"] = util
    vehicle["status"] = "DISPATCHED" if status == "ACTIVE" else status
    vehicle["route"] = route_id

    log_event("ROUTE", route_id,
               f"Route built: {load} kg via {vehicle['id']}, utilization {util}%",
               status=status)
    log_audit("ROUTE_CREATED", actor, route_id, None, route, f"Route for match {match_id}")
    return route


def find_consolidation_candidates(route_id: str) -> list[dict]:
    """
    Look for OTHER existing low-utilization routes sharing the same
    vehicle type / cold-chain requirement and a compatible destination
    direction, that could be combined with this one. Never fabricates
    resources — only proposes combining routes/resources that already
    exist in the Digital Twin.
    """
    state = get_state()
    route = state["routes"][route_id]
    candidates = []
    for other_id, other in state["routes"].items():
        if other_id == route_id or other["status"] not in ("ACTIVE", "REROUTE_REQUIRED"):
            continue
        if other.get("consolidated"):
            continue
        vehicle = state["vehicles"][route["vehicle_id"]]
        other_vehicle = state["vehicles"][other["vehicle_id"]]
        cold_match = (
            state["resources"].get(state["matches"][route["match_ids"][0]]["resource_id"], {}).get("cold_chain_required")
            == state["resources"].get(state["matches"][other["match_ids"][0]]["resource_id"], {}).get("cold_chain_required")
        )
        if not cold_match:
            continue
        combined_load = route["quantity_kg"] + other["quantity_kg"]
        if combined_load > vehicle["capacity_kg"]:
            continue
        projected_util = utilization_pct(combined_load, vehicle["capacity_kg"])
        candidates.append({
            "other_route_id": other_id,
            "current_load_kg": route["quantity_kg"],
            "other_load_kg": other["quantity_kg"],
            "combined_load_kg": combined_load,
            "current_utilization_pct": route["utilization_pct"],
            "projected_utilization_pct": projected_util,
            "additional_distance_km": other["distance_km"],  # simplification: prototype-level estimate
            "vehicle_id": route["vehicle_id"],
        })
    candidates.sort(key=lambda c: c["projected_utilization_pct"], reverse=True)
    return candidates


def apply_consolidation(route_id: str, other_route_id: str, actor="Fleet Engine") -> dict:
    state = get_state()
    route = state["routes"][route_id]
    other = state["routes"][other_route_id]
    before_route, before_other = copy.deepcopy(route), copy.deepcopy(other)

    vehicle = state["vehicles"][route["vehicle_id"]]
    combined_load = route["quantity_kg"] + other["quantity_kg"]

    route["match_ids"] = list(set(route["match_ids"] + other["match_ids"]))
    route["quantity_kg"] = combined_load
    route["utilization_pct"] = utilization_pct(combined_load, vehicle["capacity_kg"])
    route["low_utilization"] = route["utilization_pct"] < LOW_UTILIZATION_THRESHOLD_PCT
    route["consolidated"] = True
    route["consolidated_from"] = [route_id, other_route_id]
    route["contributing_resources"] = [
        state["matches"][m]["resource_id"] for m in route["match_ids"]
    ]

    other["status"] = "MERGED_INTO_" + route_id
    other["consolidated"] = True

    vehicle["current_load_kg"] = combined_load
    vehicle["utilization_pct"] = route["utilization_pct"]

    log_event("CONSOLIDATION", route_id,
               f"CONSOLIDATED ROUTE: combined with {other_route_id}, utilization now {route['utilization_pct']}%",
               status="CONSOLIDATED")
    log_audit("ROUTE_CONSOLIDATED", actor, route_id, before_route, route,
               f"Merged {other_route_id} into {route_id}")
    return route


def apply_scenario(scenario: str, params: dict, actor="Scenario Simulator"):
    """
    Apply a what-if change to the live Digital Twin state and log it.
    scenario in: ROAD_DISRUPTION, VEHICLE_UNAVAILABLE, RESOURCE_REDUCTION, DEMAND_INCREASE
    """
    state = get_state()

    if scenario == "ROAD_DISRUPTION":
        road = state["nodes"][params["road_id"]]
        before = copy.deepcopy(road)
        road["status"] = "BLOCKED"
        road["risk_level"] = "HIGH"
        road["obstruction_signal"] = "Simulated disruption"
        log_event("SCENARIO", road["id"], "Simulated road disruption applied", status="BLOCKED")
        log_audit("SCENARIO_APPLIED", actor, road["id"], before, road, "What-if: road disruption")
        for r in state["routes"].values():
            if r.get("source_node") and road_status_between(r["source_node"], r["demand_node"]) is road:
                r["status"] = "REROUTE_REQUIRED"

    elif scenario == "VEHICLE_UNAVAILABLE":
        vehicle = state["vehicles"][params["vehicle_id"]]
        before = copy.deepcopy(vehicle)
        vehicle["availability"] = "UNAVAILABLE"
        vehicle["status"] = "OFFLINE"
        log_event("SCENARIO", vehicle["id"], "Simulated vehicle breakdown applied", status="OFFLINE")
        log_audit("SCENARIO_APPLIED", actor, vehicle["id"], before, vehicle, "What-if: vehicle unavailable")

    elif scenario == "RESOURCE_REDUCTION":
        node = state["nodes"][params["farm_id"]]
        before = copy.deepcopy(node)
        factor = params.get("factor", 0.5)
        node["available_qty"] = round(node["available_qty"] * factor, 1)
        log_event("SCENARIO", node["id"], f"Simulated resource reduction to {node['available_qty']} kg")
        log_audit("SCENARIO_APPLIED", actor, node["id"], before, node, "What-if: resource reduction")

    elif scenario == "DEMAND_INCREASE":
        node = state["nodes"][params["hotel_id"]]
        before = copy.deepcopy(node)
        delta = params.get("delta_kg", 100)
        node["current_demand_kg"] += delta
        node["shortage_risk"] = "HIGH"
        log_event("SCENARIO", node["id"], f"Simulated demand increase (+{delta} kg)")
        log_audit("SCENARIO_APPLIED", actor, node["id"], before, node, "What-if: demand increase")
