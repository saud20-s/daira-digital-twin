"""
carbon_cost_calculator.py

Transparent cost / CO2 / circular-value math. Every figure the UI
shows is reproducible from these functions — no hidden aggregation.
"""

from __future__ import annotations

LOCAL_SOURCING_VALUE_PER_KG = 4.5     # SAR/kg — value of sourcing locally vs importing
AVOIDED_WASTE_VALUE_PER_KG = 6.0      # SAR/kg — value of produce that would otherwise spoil


def transport_cost(distance_km: float, vehicle: dict) -> float:
    return round(distance_km * vehicle["cost_per_km"], 2)


def transport_co2(distance_km: float, vehicle: dict) -> float:
    return round(distance_km * vehicle["co2_per_km_kg"], 2)


def circular_value(quantity_kg: float, distance_km: float, vehicle: dict) -> dict:
    local_sourcing_value = round(quantity_kg * LOCAL_SOURCING_VALUE_PER_KG, 2)
    avoided_waste_value = round(quantity_kg * AVOIDED_WASTE_VALUE_PER_KG, 2)
    cost = transport_cost(distance_km, vehicle)
    co2 = transport_co2(distance_km, vehicle)
    value = round(local_sourcing_value + avoided_waste_value - cost, 2)
    return {
        "local_sourcing_value": local_sourcing_value,
        "avoided_waste_value": avoided_waste_value,
        "transport_cost": cost,
        "transport_co2_kg": co2,
        "circular_value": value,
        "formula": "Circular Value = Local Sourcing Value + Avoided Waste Value - Transport Cost",
    }


def utilization_pct(load_kg: float, capacity_kg: float) -> float:
    if capacity_kg <= 0:
        return 0.0
    return round((load_kg / capacity_kg) * 100, 2)
