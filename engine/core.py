"""Deterministic, synthetic supply chain decision model. No external data or LLM."""
from dataclasses import dataclass
from typing import Dict, List
import networkx as nx
import pandas as pd

NODES = [
 ('PORT_SZ','Port','Shenzhen Port'),('PORT_SG','Port','Singapore Port'),
 ('SUP_T2','Tier 2','Precision Materials'),('SUP_T1','Tier 1','Apex Components'),
 ('SUP_ALT','Tier 1','Nova Components (qualified)'),
 ('CMP_C109','Component','Controller C109'),('CMP_C210','Component','Sensor C210'),
 ('PLANT_BLR','Plant','Bengaluru Assembly'),('PLANT_PUN','Plant','Pune Assembly'),
 ('PROD_P20','Product','Industrial Gateway P20'),('PROD_P30','Product','Smart Controller P30'),
 ('CUST_A','Customer','Enterprise Customer A'),('CUST_B','Customer','Enterprise Customer B')]
# Dependency direction: upstream -> downstream. Route edges are for propagation only.
EDGES = [
 ('PORT_SZ','SUP_T2'),('SUP_T2','SUP_T1'),('SUP_T1','CMP_C109'),
 ('SUP_T1','CMP_C210'),('CMP_C109','PLANT_BLR'),('CMP_C210','PLANT_PUN'),
 ('PLANT_BLR','PROD_P20'),('PLANT_PUN','PROD_P30'),
 ('PROD_P20','CUST_A'),('PROD_P30','CUST_B'),
 ('PORT_SG','SUP_ALT')]
# All monetary amounts are synthetic USD. Each product is assumed to use one relevant component per unit.
EXPOSURE = pd.DataFrame([
 {'product':'PROD_P20','component':'CMP_C109','plant':'PLANT_BLR','customer':'CUST_A','daily_units':180,'inventory_units':1080,'unit_revenue':800,'unit_margin':210,'priority':3},
 {'product':'PROD_P30','component':'CMP_C210','plant':'PLANT_PUN','customer':'CUST_B','daily_units':110,'inventory_units':990,'unit_revenue':1250,'unit_margin':350,'priority':2},
])
EVENTS = {
 'Shenzhen port disruption': {'node':'PORT_SZ','days':14,'description':'Inbound material flow through Shenzhen interrupted'},
 'Tier-2 material supplier outage': {'node':'SUP_T2','days':12,'description':'Precision Materials stops shipments'},
 'Tier-1 component supplier outage': {'node':'SUP_T1','days':10,'description':'Apex Components temporarily unavailable'},
}


def graph():
    g=nx.DiGraph()
    for node,kind,label in NODES:g.add_node(node,kind=kind,label=label)
    g.add_edges_from(EDGES)
    return g


def affected_nodes(event_node):
    g=graph()
    if event_node not in g: raise ValueError('Unknown disruption node')
    return {event_node}|nx.descendants(g,event_node)


def exposure(event_node, disruption_days, demand_factor=1.0):
    if disruption_days<0 or demand_factor<=0: raise ValueError('Invalid scenario inputs')
    impacted=affected_nodes(event_node)
    rows=[]
    for r in EXPOSURE.to_dict('records'):
        if r['product'] not in impacted: continue
        daily=r['daily_units']*demand_factor
        coverage=r['inventory_units']/daily
        shortfall=max(0., disruption_days-coverage)
        lost_units=shortfall*daily
        rows.append({**r,'daily_demand':daily,'coverage_days':coverage,
                     'shortfall_days':shortfall,'at_risk_units':lost_units,
                     'revenue_exposure':lost_units*r['unit_revenue'],
                     'margin_exposure':lost_units*r['unit_margin']})
    return pd.DataFrame(rows)


def options(event_node, disruption_days, demand_factor=1.0, max_cost=500000, min_service=0.85):
    """Compare response bundles against explicit demo assumptions. No fabricated ML confidence."""
    df=exposure(event_node,disruption_days,demand_factor)
    if df.empty:return pd.DataFrame(),df
    total_units=float((df.daily_demand*disruption_days).sum())
    lost=float(df.at_risk_units.sum())
    # Recovery is a scenario assumption: fraction of uncovered demand recovered.
    # Feasibility constraints are illustrative and should be replaced by operational data.
    strategies=[
      ('Wait / no intervention',0,0.0,0,'No mitigation; accept uncovered demand'),
      ('Expedite critical components',230000,0.90,2,'Airfreight for constrained components; capacity assumed available'),
      ('Qualified alternate supplier',115000,0.65,6,'Approved supplier; ramp-up and lead time constrain recovery'),
      ('Cross-plant inventory reallocation',70000,0.50,3,'Transfer inventory; donor-plant service impact not modeled'),
      ('Hybrid: reallocate + expedite',185000,0.95,3,'Targeted transfers plus limited expedite capacity'),
    ]
    records=[]
    for name,cost,recovery,lead,explanation in strategies:
        residual=lost*(1-recovery)
        service=1-residual/total_units if total_units else 1.
        # Expected economic cost = response spend + margin at risk proportional to remaining uncovered units.
        margin=float(df.margin_exposure.sum())*(1-recovery)
        feasible=cost<=max_cost and service>=min_service and lead<=disruption_days
        records.append({'option':name,'incremental_cost':cost,'recovery_fraction':recovery,
          'response_lead_days':lead,'service_level':service,'remaining_at_risk_units':residual,
          'remaining_margin_exposure':margin,'estimated_total_cost':cost+margin,
          'feasible':feasible,'assumptions':explanation})
    return pd.DataFrame(records).sort_values(['estimated_total_cost','incremental_cost']).reset_index(drop=True),df


def recommendation(opts):
    if opts.empty:return None
    feasible=opts[opts.feasible]
    if feasible.empty:return None
    return feasible.sort_values(['estimated_total_cost','incremental_cost']).iloc[0].to_dict()


def explain(row, exp):
    if row is None:return 'No option satisfies the selected cost, service, and timing constraints. Escalate for manual review.'
    return (f"Recommend **{row['option']}** among feasible scenarios. Estimated response spend: "
            f"${row['incremental_cost']:,.0f}; modeled service level: {row['service_level']:.1%}; "
            f"remaining margin exposure: ${row['remaining_margin_exposure']:,.0f}. "
            f"The recommendation minimizes response spend plus modeled remaining margin exposure "
            f"subject to the selected budget, service, and timing constraints. "
            f"It relies on **synthetic inventory, demand, recovery and cost assumptions**; "
            f"verify supplier capacity, route availability, qualification and donor impacts before approval.")
