"""
approval_workflow.py

Human-in-the-loop gate. Nothing an AI module produces (aerial
detection, recommendation) is allowed to change the Digital Twin's
operational state without passing through here and being recorded
in the audit trail.
"""

from __future__ import annotations
import copy

from models import get_state, new_id, now_str, log_event, log_audit


def validate_detection(detection_id: str, decision: str, validated_qty=None,
                        resource_type=None, actor="Operations Manager", notes=""):
    """
    decision: "APPROVE" | "REJECT" | "REANALYZE"
    Promotes an aerial detection into a confirmed Digital Twin resource
    (for RESOURCE mode) or an infrastructure condition (for
    INFRASTRUCTURE mode) — only on APPROVE.
    """
    state = get_state()
    detection = state["aerial_detections"][detection_id]
    before = copy.deepcopy(detection)

    if decision == "REJECT":
        detection["validation_status"] = "REJECTED"
        log_event("VALIDATION", detection["target_entity"], "Detection rejected by operator", status="REJECTED")
        log_audit("DETECTION_REJECTED", actor, detection_id, before, detection, notes or "Rejected by human review")
        return None

    if decision == "REANALYZE":
        detection["validation_status"] = "PENDING_REVIEW"
        log_event("VALIDATION", detection["target_entity"], "Re-analysis requested", status="REVIEW_REQUIRED")
        return None

    # APPROVE
    detection["validation_status"] = "HUMAN_VALIDATED"
    entity_id = detection["target_entity"]

    if detection["mode"] == "RESOURCE":
        qty = validated_qty if validated_qty is not None else detection["estimated_quantity_kg"]
        r_type = resource_type or "FRESH_PRODUCE"
        resource_id = new_id("AERIAL-FARM")
        resource = {
            "resource_id": resource_id,
            "source_node": entity_id,
            "resource_type": r_type,
            "quantity": qty,
            "unit": "kg",
            "confidence": detection["confidence"],
            "validation_status": "HUMAN_VALIDATED",
            "source": "AERIAL_INTELLIGENCE",
            "timestamp": now_str(),
            "cold_chain_required": True,
            "available_for_matching": True,
            "notes": notes,
        }
        state["resources"][resource_id] = resource

        node = state["nodes"][entity_id]
        node_before = copy.deepcopy(node)
        node["resource_type"] = r_type
        node["available_qty"] = qty
        node["confidence"] = detection["confidence"]
        node["harvest_status"] = "AVAILABLE"
        node["matching_available"] = True
        node["status"] = "ACTIVE"
        node["last_aerial_obs"] = now_str()
        node["last_field_update"] = now_str()
        node["source"] = "AERIAL_INTELLIGENCE"

        log_event("VALIDATION", entity_id, f"{qty} kg {r_type} validated with human review",
                   confidence=detection["confidence"], status="VALIDATED_WITH_HUMAN_REVIEW")
        log_audit("RESOURCE_VALIDATED", actor, entity_id, node_before, node,
                   notes or f"Validated {qty} kg {r_type} from aerial detection {detection_id}")
        log_event("DIGITAL_TWIN_UPDATE", entity_id, "Digital Twin node updated with validated resource")
        return resource_id

    else:  # INFRASTRUCTURE
        road = state["nodes"][entity_id]
        road_before = copy.deepcopy(road)
        road["status"] = "REVIEW_REQUIRED"
        road["risk_level"] = "HIGH" if detection["category"] == "POTENTIAL_OBSTRUCTION" else "MEDIUM"
        road["obstruction_signal"] = detection["category_label"]
        road["last_inspection"] = now_str()

        log_event("VALIDATION", entity_id, f"{detection['category_label']} confirmed for human review",
                   confidence=detection["confidence"], status="REVIEW_REQUIRED")
        log_audit("INFRASTRUCTURE_CONDITION_VALIDATED", actor, entity_id, road_before, road,
                   notes or f"Confirmed {detection['category_label']} from aerial detection {detection_id}")
        log_event("DIGITAL_TWIN_UPDATE", entity_id, "Road status changed — route optimization will reconsider")
        return entity_id


def decide_on_recommendation(rec_id: str, decision: str, actor="Operations Manager", reason=""):
    """
    decision: "APPROVE" | "MODIFY" | "REJECT"
    Records the human decision on an AI recommendation into the audit
    trail and decision log. Does not itself re-run optimization —
    the caller (UI layer) triggers recomputation after MODIFY.
    """
    state = get_state()
    rec = state["recommendations"][rec_id]
    before = copy.deepcopy(rec)
    rec["human_decision"] = decision
    rec["decision_reason"] = reason
    rec["decided_by"] = actor
    rec["decided_at"] = now_str()

    decision_record = {
        "decision_id": new_id("DEC"),
        "recommendation_id": rec_id,
        "actor": actor,
        "timestamp": now_str(),
        "decision": decision,
        "previous_state": before.get("action"),
        "new_state": decision,
        "reason": reason,
        "affected_entities": rec.get("affected_entities", []),
    }
    state["decisions"].append(decision_record)
    log_audit("RECOMMENDATION_DECISION", actor, rec_id, before, rec, reason or f"Operator chose {decision}")
    log_event("DECISION", rec_id, f"Operator {decision} recommendation: {rec['action']}", status=decision)
    return decision_record
