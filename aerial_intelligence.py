"""
aerial_intelligence.py

Heuristic, transparent "AI screening" layer over uploaded imagery.
This is explicitly a PROTOTYPE SCREENING LAYER, not a certified
engineering or agricultural measurement system. It produces a
detection + confidence score that must be human-validated before
it is allowed to touch the Digital Twin state.
"""

from __future__ import annotations
import numpy as np
from PIL import Image

from models import new_id, log_event, get_state

DETECTION_CATEGORIES = [
    "AGRICULTURE_VEGETATION",
    "RESOURCE_AVAILABILITY",
    "DRY_BARE_AREA",
    "ROAD_INFRASTRUCTURE_SIGNAL",
    "POTENTIAL_OBSTRUCTION",
    "POTENTIAL_LANDSLIDE_DEBRIS",
    "WATER_RELATED_SIGNAL",
    "UNKNOWN_ANOMALY",
]

CATEGORY_LABELS = {
    "AGRICULTURE_VEGETATION": "Agriculture / Vegetation Signal",
    "RESOURCE_AVAILABILITY": "Resource Availability Signal",
    "DRY_BARE_AREA": "Dry / Bare Area Signal",
    "ROAD_INFRASTRUCTURE_SIGNAL": "Road / Infrastructure Signal",
    "POTENTIAL_OBSTRUCTION": "Potential Road Obstruction",
    "POTENTIAL_LANDSLIDE_DEBRIS": "Potential Landslide / Debris Signal",
    "WATER_RELATED_SIGNAL": "Water-Related Signal",
    "UNKNOWN_ANOMALY": "Unknown Anomaly",
}


def analyze_image(image: Image.Image, mode: str, target_entity: str) -> dict:
    """
    Run a heuristic screening pass over an uploaded drone image.

    mode: "RESOURCE" -> screen for vegetation / fresh-produce signal
          "INFRASTRUCTURE" -> screen for obstruction / road-damage signal

    Returns a raw, UNVALIDATED detection record. Nothing here is
    written into the Digital Twin — see approval_workflow.py for the
    human-validation gate that promotes a detection into a resource
    or an infrastructure condition.
    """
    img = image.convert("RGB").resize((160, 160))
    arr = np.asarray(img).astype(float) / 255.0
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    green_mask = (g > r) & (g > b) & (g > 0.25)
    green_ratio = float(green_mask.mean())

    brightness = (r + g + b) / 3.0
    brown_gray_mask = (np.abs(r - g) < 0.12) & (np.abs(g - b) < 0.12) & (brightness > 0.25) & (brightness < 0.75)
    bare_ratio = float(brown_gray_mask.mean())

    dark_mask = brightness < 0.22
    dark_ratio = float(dark_mask.mean())

    blue_mask = (b > r) & (b > g)
    water_ratio = float(blue_mask.mean())

    detection_id = new_id("DET")

    if mode == "RESOURCE":
        category = "AGRICULTURE_VEGETATION" if green_ratio > 0.15 else "DRY_BARE_AREA"
        # crude, transparent heuristic: more green pixel coverage -> higher
        # estimated fresh-produce signal. Deliberately simple & explainable.
        estimated_qty_kg = round(green_ratio * 300, 1)
        confidence = round(min(0.95, max(0.05, green_ratio * 1.6)) * 100, 1)
        signal_label = CATEGORY_LABELS[category]
    else:  # INFRASTRUCTURE
        if dark_ratio > 0.18 or bare_ratio > 0.55:
            category = "POTENTIAL_OBSTRUCTION"
        elif water_ratio > 0.2:
            category = "WATER_RELATED_SIGNAL"
        else:
            category = "ROAD_INFRASTRUCTURE_SIGNAL"
        estimated_qty_kg = None
        confidence = round(min(0.95, max(0.05, (dark_ratio + bare_ratio) * 1.2)) * 100, 1)
        signal_label = CATEGORY_LABELS[category]

    detection = {
        "detection_id": detection_id,
        "mode": mode,
        "target_entity": target_entity,
        "category": category,
        "category_label": signal_label,
        "confidence": confidence,
        "estimated_quantity_kg": estimated_qty_kg,
        "green_ratio": round(green_ratio, 3),
        "bare_ratio": round(bare_ratio, 3),
        "dark_ratio": round(dark_ratio, 3),
        "water_ratio": round(water_ratio, 3),
        "validation_status": "PENDING_REVIEW",
        "requires_human_validation": True,
        "source": "AERIAL_INTELLIGENCE",
    }

    state = get_state()
    state["aerial_detections"][detection_id] = detection

    log_event(
        event_type="AERIAL_OBSERVATION",
        entity=target_entity,
        signal=f"AI Screening Signal — {signal_label}",
        confidence=confidence,
        status="REVIEW_REQUIRED",
    )

    return detection
