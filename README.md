# Supply Chain Decision Intelligence — V1 Portfolio POC

A runnable Streamlit demonstration of a **single, coherent enterprise decision workflow**:

**Disruption → Dependency Graph → Business Exposure → Response Comparison → Explainable Recommendation → Human Approval**

All data and numerical assumptions are **synthetic**. No real ERP, supplier or customer systems are connected. No external AI model is used.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Community Cloud

Upload the contents of this folder to a GitHub repository and set the main file path to `app.py`. There are no credentials or secrets required.

## Demonstration (90 seconds)

1. Choose **Shenzhen port disruption** and set duration to 14 days.
2. Show the affected entities, products and economic exposure on **Event & KPIs**.
3. Open **Dependency Graph** to trace the disruption to two downstream products and customers.
4. Open **Business Impact** to show inventory coverage and uncovered demand.
5. Open **Response Scenarios** to compare waiting, expediting, alternate supplier, reallocation and hybrid response under budget/service constraints.
6. Open **Decision Explanation** to see why the cheapest *feasible* modeled option is recommended.
7. Open **Governance & Audit**; approve with a reviewer and rationale; download the audit JSON.
8. Change budget or service requirement to demonstrate a recalculated decision.

## Model assumptions

- Edges point upstream → downstream; reachability is interpreted as potential dependency exposure, not proof of a real material shortage.
- One relevant component is required per finished product unit.
- Inventory coverage = available inventory / daily demand.
- At-risk units = max(0, disruption days − coverage days) × daily demand.
- Revenue and margin exposure = at-risk units × synthetic unit economics.
- Options recover a fixed, synthetic fraction of at-risk units. This is a teaching assumption, **not** optimized shipping or sourcing feasibility.
- Modeled service level = 1 − remaining at-risk units / affected demand during disruption.
- Estimated total cost = response spend + remaining modeled margin exposure.
- Feasible options meet budget, service and response lead-time constraints.
- Lowest estimated total cost among feasible options is recommended.
- Approval is a **session-only** event and does not trigger any external action.

## Architecture

`engine/core.py`: directed dependency graph, exposure engine, scenario options, constraint evaluation and grounded explanation.

`app.py`: Streamlit interactive UI, Plotly network visualization, review and audit export.

`tests/test_core.py`: basic model checks.

## Next increments (not claimed as implemented)

- SKU/BOM and shipment-level provenance; supplier/facility entity resolution.
- Explicit material-flow, alternate-path, production and transport capacity constraints.
- Scenario optimization using OR-Tools / mixed-integer programming.
- Sensitivity analysis, uncertainty bands and demand scenarios.
- Persistence with Postgres, immutable audit, RBAC and external integrations.
- Optional grounded LLM explanation with tools and approval gates.

**Do not represent this POC as a production-grade digital twin, autonomous AI agent or verified supplier risk system.**

## V2 — Capacity-aware recovery optimization (new)

V2 retains all seven V1 tabs and adds **BOM & Capacity**, **Recovery Optimizer**, and **Sensitivity Analysis** (10 horizontal tabs total). Three additional sidebar controls model alternate supplier capacity, transport capacity, and extra response delays.

The V2 optimizer uses SciPy HiGHS linear programming. Its variables are recoverable finished-product units allocated from each eligible recovery source. It minimizes **response spending + uncovered contribution margin** subject to: uncovered demand per product, source component capacity, shared route capacity, response budget, response lead time, and minimum service level. When the minimum service target is impossible, the application explicitly flags the target as unmet and displays a diagnostic maximum-recovery allocation rather than pretending a feasible solution exists.

**Important model limitations:** synthetic data; a simplified BOM with a designated High-criticality bottleneck component for each finished product; other components assumed available; response quantities are limited to demand after response arrival; supplier capacity is a fixed scenario assumption; transfer capacities are net of protected donor safety stock; no discrete shipment sizes, full manufacturing scheduling, real ERP integrations, uncertainty quantification, or autonomous execution. V1's predefined response comparisons remain visible as a legacy baseline; use the **Recovery Optimizer** tab for V2 capacity-based recommendations. The V1 governance tab records approval of the **V1** recommendation only, not the V2 optimization result; do not interpret it as an approval workflow for V2 allocations.

Run automated checks:

```bash
python -m unittest discover -s tests -v
```
