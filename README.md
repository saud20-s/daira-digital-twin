# DA'IRA — دائرة
### Circular Intelligence Digital Twin for Soudah

An operational-intelligence prototype (not a dashboard) that closes the loop:

```
REAL WORLD → AERIAL INTELLIGENCE → AI ANALYSIS → HUMAN VALIDATION →
DIGITAL TWIN UPDATE → RESOURCE/DEMAND MATCH → FLEET OPTIMIZATION →
CIRCULAR VALUE → AI RECOMMENDATION → HUMAN DECISION → AUDIT TRAIL →
UPDATED DIGITAL TWIN
```

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

## Fastest way to see the full loop

1. Launch the app.
2. In the sidebar, click **▶ Run Guided Demonstration**.
3. This walks a synthetic drone observation on `FARM-01` through screening →
   human validation → matching → routing → consolidation check → AI
   recommendation, live in the main panel and the event feed.
4. Go to **9 · Decision Center** to approve/modify/reject the generated
   recommendation.
5. Go to **10 · Audit Trail** to inspect the full before/after lineage of
   every state change, and export the entire Digital Twin state as JSON.

## Manual walkthrough

- **2 · Aerial Intelligence** — upload your own drone image, or use the
  built-in synthetic sample, in `RESOURCE` mode (screens for
  vegetation/produce signal) or `INFRASTRUCTURE` mode (screens for
  obstruction/road-condition signal). Every detection is heuristic and
  requires human Approve/Reject/Re-analyze before it touches the twin.
- **3 · Digital Twin** — network view of the hub, farms, hotels, roads,
  and active resource flows, colour-coded by operational state.
- **4 · Resource & Demand** — validated resources and live demand
  coverage per hotel.
- **5 · Matching Engine** — pick a validated resource, see every
  compatible hotel scored with a transparent breakdown (confidence,
  demand coverage, compatibility, distance, urgency), and create a match.
- **6 · Fleet & Routes** — build a route for a match, see utilization,
  cost, CO₂, and circular value; low-utilization routes trigger a
  consolidation recommendation against other real, existing routes only.
- **7 · Scenario Simulator** — apply what-ifs (road disruption, vehicle
  breakdown, resource reduction, demand increase) and inspect the
  before/after Timeline.
- **8 · AI Recommendations** — generate an explainable recommendation
  (DISPATCH / CONSOLIDATE / HOLD FOR REVIEW / REROUTE / WAIT FOR MORE
  DATA / REJECT) from the actual current state.
- **9 · Decision Center** — human Approve / Modify / Reject on every
  recommendation, logged with actor, timestamp, and reason.
- **10 · Audit Trail** — full immutable audit log with before/after
  state per event, the raw event feed, and a JSON export of the whole
  Digital Twin state.

## Architecture

| Module | Responsibility |
|---|---|
| `models.py` | Entity schemas + single source-of-truth `STATE`, event log, audit log |
| `aerial_intelligence.py` | Heuristic CV screening over drone images (never writes to state directly) |
| `approval_workflow.py` | Human-in-the-loop gate: promotes validated detections into resources/conditions; records decisions |
| `matching_engine.py` | Resource → demand scoring and match creation, with lineage rule enforcement |
| `circular_router.py` | Vehicle selection, route building, consolidation search/apply, scenario simulation |
| `carbon_cost_calculator.py` | Transparent cost / CO₂ / circular-value formulas |
| `recommendation_engine.py` | Explainable AI recommendation derived from live route state |
| `app.py` | Streamlit command-center UI (10 sections) |

**Design rules enforced in code:** matched quantity can never exceed the
validated resource quantity or the receiver's remaining demand; route
quantity always equals the sum of its assigned matches; consolidated
routes are explicitly labeled and list every contributing resource; no
quantity is ever silently invented — everything traces back to an
aerial detection or a seed value you can inspect in the Digital Twin
entity inspector.

## Honesty note

The computer-vision screening in this prototype is a simple, explainable
heuristic (colour-ratio analysis) built to demonstrate the *architecture*
of an aerial-intelligence-driven digital twin — it is explicitly **not**
a certified engineering or agricultural measurement system, and the UI
labels every detection as an "AI Screening Signal" requiring human
validation.
