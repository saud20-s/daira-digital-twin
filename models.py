"""
DA'IRA — Circular Intelligence Digital Twin for Soudah
models.py

Defines the entity schemas and the single source-of-truth operational
state for the whole Digital Twin. Every module reads from and writes
to STATE via the helper functions in this file — there are no isolated
hard-coded values anywhere else in the app.
"""

from __future__ import annotations
import copy
import uuid
from datetime import datetime

import streamlit as st

# ---------------------------------------------------------------------
# Time helper (kept in one place so the whole prototype uses one clock)
# ---------------------------------------------------------------------

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


# ---------------------------------------------------------------------
# Seed data — the initial physical + operational picture of Soudah
# ---------------------------------------------------------------------

def _seed_state() -> dict:
    return {
        "nodes": {
            "HUB-01": {
                "id": "HUB-01", "type": "HUB", "name": "Abha Central Logistics Hub",
                "location": (18.2465, 42.5053), "elevation_m": 2270,
                "storage_capacity_kg": 5000, "current_inventory_kg": 0,
                "status": "ACTIVE", "alerts": [],
                "last_update": now_str(), "source": "SEED",
            },
            "FARM-01": {
                "id": "FARM-01", "type": "FARM", "name": "Al-Souda Terraced Farms",
                "location": (18.2660, 42.3630), "elevation_m": 2900,
                "resource_type": None, "available_qty": 0, "confidence": 0.0,
                "harvest_status": "UNKNOWN", "waste_risk": "LOW",
                "cold_chain_required": True, "matching_available": False,
                "status": "IDLE", "last_aerial_obs": None, "last_field_update": now_str(),
                "source": "SEED",
            },
            "FARM-02": {
                "id": "FARM-02", "type": "FARM", "name": "Bani Mazen Orchard Cooperative",
                "location": (18.2110, 42.4020), "elevation_m": 2450,
                "resource_type": None, "available_qty": 0, "confidence": 0.0,
                "harvest_status": "UNKNOWN", "waste_risk": "LOW",
                "cold_chain_required": True, "matching_available": False,
                "status": "IDLE", "last_aerial_obs": None, "last_field_update": now_str(),
                "source": "SEED",
            },
            "HOTEL-01": {
                "id": "HOTEL-01", "type": "HOTEL", "name": "Tahlal Ridge Hotel & Spa",
                "location": (18.2530, 42.3800), "elevation_m": 2600,
                "demand_type": "FRESH_PRODUCE", "current_demand_kg": 600,
                "forecast_demand_kg": 700, "cold_chain_required": True,
                "current_inventory_kg": 40, "service_status": "OPERATING",
                "supply_status": "SHORTAGE", "shortage_risk": "MEDIUM",
                "status": "ACTIVE", "source": "SEED", "last_update": now_str(),
            },
            "HOTEL-02": {
                "id": "HOTEL-02", "type": "HOTEL", "name": "Soudah Peaks Cliff Resort",
                "location": (18.2705, 42.3910), "elevation_m": 2810,
                "demand_type": "FRESH_PRODUCE", "current_demand_kg": 300,
                "forecast_demand_kg": 320, "cold_chain_required": True,
                "current_inventory_kg": 60, "service_status": "OPERATING",
                "supply_status": "STABLE", "shortage_risk": "LOW",
                "status": "ACTIVE", "source": "SEED", "last_update": now_str(),
            },
            "ROAD-01": {
                "id": "ROAD-01", "type": "ROAD", "name": "Soudah Ridge Access Road",
                "connects": ("FARM-01", "HOTEL-01"), "status": "ACTIVE",
                "risk_level": "LOW", "last_inspection": now_str(),
                "obstruction_signal": None, "source": "SEED",
            },
            "ROAD-02": {
                "id": "ROAD-02", "type": "ROAD", "name": "Bani Mazen Corridor",
                "connects": ("FARM-02", "HOTEL-02"), "status": "ACTIVE",
                "risk_level": "LOW", "last_inspection": now_str(),
                "obstruction_signal": None, "source": "SEED",
            },
        },
        "vehicles": {
            "VEH-01": {
                "id": "VEH-01", "type": "Refrigerated Rigid 7.5t", "capacity_kg": 3500,
                "current_load_kg": 0, "utilization_pct": 0.0, "cold_chain": True,
                "location": "HUB-01", "availability": "AVAILABLE", "status": "IDLE",
                "route": None, "cost_per_km": 3.4, "co2_per_km_kg": 0.85,
            },
            "VEH-02": {
                "id": "VEH-02", "type": "Light Box Truck 3.5t", "capacity_kg": 1500,
                "current_load_kg": 0, "utilization_pct": 0.0, "cold_chain": False,
                "location": "HUB-01", "availability": "AVAILABLE", "status": "IDLE",
                "route": None, "cost_per_km": 2.1, "co2_per_km_kg": 0.55,
            },
        },
        "resources": {},      # resource_id -> resource record
        "demands": {},        # derived view, recomputed from nodes on read
        "events": [],         # chronological event feed
        "matches": {},        # match_id -> match record
        "routes": {},         # route_id -> route record
        "recommendations": {},# rec_id -> recommendation record
        "decisions": [],      # audit-linked human decisions
        "audit_trail": [],    # immutable audit log
        "aerial_detections": {},  # detection_id -> raw AI detection, pre-validation
        "timeline_snapshots": [],  # named before/after snapshots for the Timeline view
    }


def get_state() -> dict:
    if "twin_state" not in st.session_state:
        st.session_state["twin_state"] = _seed_state()
    return st.session_state["twin_state"]


def reset_state():
    st.session_state["twin_state"] = _seed_state()


# ---------------------------------------------------------------------
# Event + audit helpers (used by every engine module)
# ---------------------------------------------------------------------

def log_event(event_type: str, entity: str, signal: str, confidence=None, status="INFO"):
    state = get_state()
    event = {
        "event_id": new_id("EVT"),
        "time": now_time(),
        "timestamp": now_str(),
        "type": event_type,
        "entity": entity,
        "signal": signal,
        "confidence": confidence,
        "status": status,
    }
    state["events"].append(event)
    return event


def log_audit(event_type: str, actor: str, entity: str, previous_state, new_state, reason: str):
    state = get_state()
    record = {
        "event_id": new_id("AUD"),
        "timestamp": now_str(),
        "event_type": event_type,
        "actor": actor,
        "entity": entity,
        "previous_state": copy.deepcopy(previous_state),
        "new_state": copy.deepcopy(new_state),
        "reason": reason,
    }
    state["audit_trail"].append(record)
    return record


def snapshot_timeline(label: str, note: str):
    """Capture a lightweight snapshot of key figures for the Timeline view."""
    state = get_state()
    snap = {
        "label": label,
        "time": now_time(),
        "note": note,
        "farms": {
            fid: {"resource_type": f.get("resource_type"), "available_qty": f.get("available_qty"),
                  "confidence": f.get("confidence")}
            for fid, f in state["nodes"].items() if f["type"] == "FARM"
        },
        "hotels": {
            hid: {"current_demand_kg": h.get("current_demand_kg"), "supply_status": h.get("supply_status")}
            for hid, h in state["nodes"].items() if h["type"] == "HOTEL"
        },
        "vehicle_utilization": {
            vid: v["utilization_pct"] for vid, v in state["vehicles"].items()
        },
    }
    state["timeline_snapshots"].append(snap)
    return snap
