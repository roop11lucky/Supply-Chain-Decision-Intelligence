"""Deterministic V3 decision orchestration; no external systems are modified."""
import hashlib
import json
from datetime import datetime, timezone

def plan_snapshot(event, days, demand_pct, budget, service, supplier_factor, transport_factor, delay, plan):
    allocations = [] if plan.allocations.empty else [
        {"source":str(r["source"]),"product":str(r["product"]),
         "recovered_units":round(float(r["recovered_product_units"]),3),
         "cost_usd":round(float(r["incremental_cost"]),2)}
        for r in plan.allocations.to_dict("records")]
    payload={"event":event,"duration_days":int(days),"demand_change_pct":int(demand_pct),
      "budget_usd":int(budget),"minimum_service":round(float(service),4),
      "supplier_capacity_factor":round(float(supplier_factor),4),
      "transport_capacity_factor":round(float(transport_factor),4),"extra_delay_days":int(delay),
      "optimized_service":round(float(plan.service_level),5),"response_cost_usd":round(float(plan.total_cost),2),
      "remaining_margin_exposure_usd":round(float(plan.margin_remaining),2),
      "meets_service_target":bool(plan.feasible),"allocations":allocations}
    canonical=json.dumps(payload,sort_keys=True,separators=(',',':'))
    payload["plan_id"]=hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return payload

def record_decision(snapshot, action, reviewer, rationale):
    if action not in ("APPROVED","REJECTED"): raise ValueError("Invalid action")
    if not reviewer.strip() or not rationale.strip(): raise ValueError("Reviewer and rationale required")
    if action=="APPROVED" and not snapshot["meets_service_target"]:
        raise ValueError("Cannot approve a plan that does not meet the minimum service constraint")
    return {"timestamp_utc":datetime.now(timezone.utc).isoformat(timespec='seconds'),
      "action":action,"reviewer":reviewer.strip(),"rationale":rationale.strip(),
      "plan":snapshot.copy(),"execution_status":"NOT_EXECUTED_DEMO_ONLY"}

def decision_brief(snapshot, plan):
    if not plan.feasible:
        return (f"The optimized response reaches {plan.service_level:.1%} service against the required "
          f"{snapshot['minimum_service']:.0%}. This plan is not approvable. Increase budget or capacity, "
          "reduce response delay, or escalate for an explicit exception outside this demo.")
    top=(plan.allocations.sort_values('recovered_product_units',ascending=False).head(3)
         if not plan.allocations.empty else None)
    sources=(', '.join(f"{r.source}: {r.recovered_product_units:,.0f} units" for r in top.itertuples())
             if top is not None else 'No recovery allocations needed')
    return (f"The optimized plan reaches {plan.service_level:.1%} modeled service with "
      f"${plan.total_cost:,.0f} response spend and ${plan.margin_remaining:,.0f} residual margin exposure. "
      f"Major recovery actions: {sources}. All figures are calculated from synthetic assumptions; "
      "verify supplier qualification, route capacity, donor effects and execution timing before action.")
