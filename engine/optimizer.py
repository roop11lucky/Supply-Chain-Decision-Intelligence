"""V2 synthetic, constraint-based recovery planning using linear programming.

All amounts and relationships are illustrative. The LP minimizes incremental spend
plus uncovered contribution margin subject to capacity, lead-time and budget limits.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from engine.core import EXPOSURE, affected_nodes

# A component-level BOM. Quantities are units of component per finished unit.
BOM = pd.DataFrame([
    {'product':'PROD_P20','component':'CMP_C109','qty_per_product':1.0,'criticality':'High'},
    {'product':'PROD_P20','component':'CMP_C210','qty_per_product':0.25,'criticality':'Medium'},
    {'product':'PROD_P30','component':'CMP_C210','qty_per_product':1.0,'criticality':'High'},
])

# Available recovery sources. Donor available units are NET of protected donor safety stock.
# Source capacity is shared across products; allocation is optimized, not pre-assigned.
SOURCES = pd.DataFrame([
    {'source':'Alternate supplier — C109','component':'CMP_C109','kind':'Supplier','capacity_units':900,'lead_days':5,'unit_cost':85,'route':'Singapore → Bengaluru','route_capacity_units':1200,'qualification':'Qualified','donor_protected_units':0},
    {'source':'Alternate supplier — C210','component':'CMP_C210','kind':'Supplier','capacity_units':520,'lead_days':6,'unit_cost':110,'route':'Singapore → Pune','route_capacity_units':650,'qualification':'Qualified','donor_protected_units':0},
    {'source':'Cross-plant reserve — C109','component':'CMP_C109','kind':'Transfer','capacity_units':460,'lead_days':2,'unit_cost':48,'route':'Pune → Bengaluru','route_capacity_units':500,'qualification':'Approved transfer','donor_protected_units':300},
    {'source':'Cross-plant reserve — C210','component':'CMP_C210','kind':'Transfer','capacity_units':300,'lead_days':3,'unit_cost':52,'route':'Bengaluru → Pune','route_capacity_units':350,'qualification':'Approved transfer','donor_protected_units':200},
    {'source':'Emergency air freight — C109','component':'CMP_C109','kind':'Expedite','capacity_units':700,'lead_days':1,'unit_cost':230,'route':'Shenzhen → Bengaluru air','route_capacity_units':700,'qualification':'Approved emergency','donor_protected_units':0},
    {'source':'Emergency air freight — C210','component':'CMP_C210','kind':'Expedite','capacity_units':360,'lead_days':1,'unit_cost':280,'route':'Shenzhen → Pune air','route_capacity_units':360,'qualification':'Approved emergency','donor_protected_units':0},
])

@dataclass
class Plan:
    status: str
    allocations: pd.DataFrame
    product_impact: pd.DataFrame
    total_cost: float
    margin_remaining: float
    service_level: float
    baseline_service: float
    avoided_margin: float
    feasible: bool
    note: str
    constraints: pd.DataFrame


def plan_recovery(event_node, disruption_days, demand_factor=1.0, budget=250000, min_service=0.85,
                  supplier_capacity_factor=1.0, transport_capacity_factor=1.0, extra_delay_days=0):
    if disruption_days < 1 or demand_factor <= 0 or budget < 0 or not 0 <= min_service <= 1:
        raise ValueError('Invalid planning parameters')
    impacted=affected_nodes(event_node)
    base=EXPOSURE.copy()
    base['daily_demand']=base.daily_units*demand_factor
    base['horizon_demand']=base.daily_demand*disruption_days
    # Only disrupted finished goods have uncovered demand; unaffected products remain served.
    base['at_risk_units']=base.apply(lambda r:max(0.,r.horizon_demand-r.inventory_units) if r['product'] in impacted else 0.,axis=1)
    base['covered_units']=base.horizon_demand-base.at_risk_units
    total_demand=float(base.horizon_demand.sum())
    total_short=float(base.at_risk_units.sum())
    base_service=1-total_short/total_demand if total_demand else 1.
    base['recovered_units']=0.
    base['remaining_units']=base.at_risk_units
    base['remaining_margin']=base.remaining_units*base.unit_margin
    if total_short <= 1e-9:
        return Plan('No recovery required',pd.DataFrame(),base,0.,0.,1.,1.,0.,True,'No uncovered demand in this scenario.',pd.DataFrame())

    # Recovery is only available when the component has a relevant path into an impacted product.
    # Conservative treatment of BOM: one unit of recovery covers the bottleneck component;
    # other BOM components are assumed available. This is not full multi-component production scheduling.
    candidates=[]
    for si,s in SOURCES.iterrows():
        lead=float(s.lead_days)+extra_delay_days
        if lead >= disruption_days:continue
        if s.qualification not in ('Qualified','Approved transfer','Approved emergency'):continue
        for pi,p in base.iterrows():
            if p.at_risk_units <= 0:continue
            relevant=BOM[(BOM['product']==p['product']) & (BOM['component']==s['component'])]
            if relevant.empty or relevant.iloc[0]['criticality'] != 'High':continue
            qty_per=float(relevant.iloc[0].qty_per_product)
            # Conservative lead-time availability: no recovered units can address demand
            # that becomes uncovered before the response arrives.
            days_after=max(0.,disruption_days-lead)
            usable_demand=min(float(p.at_risk_units),float(p.daily_demand)*days_after)
            if usable_demand <= 0:continue
            candidates.append({'source_idx':si,'product_idx':pi,'source':s['source'],
              'product':p['product'],'component':s['component'],'kind':s['kind'],
              'route':s['route'],'lead_days':lead,'unit_cost':float(s.unit_cost)*qty_per,
              'qty_per_product':qty_per,'max_recovery':usable_demand,'margin':float(p.unit_margin)})
    if not candidates:
        return Plan('No available recovery sources',pd.DataFrame(),base,0.,float(base.remaining_margin.sum()),base_service,base_service,0.,base_service>=min_service,'No qualified recovery sources arrive in time.',pd.DataFrame())

    n=len(candidates)
    # Each variable is finished-product units recovered by a source.
    # Primary economic objective: response cost - avoided contribution margin.
    c=np.array([a['unit_cost']-a['margin'] for a in candidates],dtype=float)
    A=[]; b=[]; constraint_names=[]
    def add_constraint(name, coefficients, rhs):
        A.append(coefficients);b.append(max(0.,float(rhs)));constraint_names.append(name)
    for pi,p in base.iterrows():
        add_constraint(f'Uncovered demand: {p["product"]}',
            [1. if a['product_idx']==pi else 0. for a in candidates],p.at_risk_units)
    for si,s in SOURCES.iterrows():
        multiplier=supplier_capacity_factor if s['kind']=='Supplier' else 1.
        add_constraint(f'Source capacity: {s["source"]}',
            [a['qty_per_product'] if a['source_idx']==si else 0. for a in candidates],s.capacity_units*multiplier)
    for route,rs in SOURCES.groupby('route'):
        # A shared route is limited by the single route-capacity declaration, not sum of sources.
        route_cap=float(rs.route_capacity_units.min())*transport_capacity_factor
        add_constraint(f'Transport capacity: {route}',
            [a['qty_per_product'] if a['route']==route else 0. for a in candidates],route_cap)
    costs=np.array([a['unit_cost'] for a in candidates],dtype=float)
    add_constraint('Response budget',costs,budget)
    # If service target is not attainable, still return the best achievable economic plan
    # and transparently flag it as infeasible instead of fabricating a feasible plan.
    bounds=[(0.,a['max_recovery']) for a in candidates]
    # Enforce the user's minimum service requirement when feasible.
    required_recovery=max(0.,total_short-(1-min_service)*total_demand)
    service_row=np.full(n,-1.,dtype=float)
    hard_A=np.vstack([np.array(A),service_row])
    hard_b=np.append(np.array(b),-required_recovery)
    result=linprog(c,A_ub=hard_A,b_ub=hard_b,bounds=bounds,method='highs')
    target_attainable=result.success
    if not target_attainable:
        # Infeasible service target: maximize recovered units under actual capacity/budget.
        # This is a diagnostic fallback, never described as an approved feasible plan.
        result=linprog(-np.ones(n),A_ub=np.array(A),b_ub=np.array(b),bounds=bounds,method='highs')
    if not result.success:
        return Plan('Solver failed',pd.DataFrame(),base,0.,float(base.remaining_margin.sum()),base_service,base_service,0.,False,result.message,pd.DataFrame())
    x=result.x
    for i,a in enumerate(candidates):
        base.loc[a['product_idx'],'recovered_units']+=float(x[i])
    base['remaining_units']=(base.at_risk_units-base.recovered_units).clip(lower=0)
    base['remaining_margin']=base.remaining_units*base.unit_margin
    total_cost=float(np.dot(costs,x))
    margin_remaining=float(base.remaining_margin.sum())
    service=1-float(base.remaining_units.sum())/total_demand
    feasible=target_attainable and service+1e-8>=min_service
    allocation_rows=[]
    for i,a in enumerate(candidates):
        if x[i]>1e-6:
            allocation_rows.append({**a,'recovered_product_units':float(x[i]),
                'component_units':float(x[i]*a['qty_per_product']),
                'incremental_cost':float(x[i]*a['unit_cost']),
                'avoided_margin':float(x[i]*a['margin'])})
    constraint_rows=[]
    for name,coeff,rhs in zip(constraint_names,A,b):
        used=float(np.dot(coeff,x))
        constraint_rows.append({'constraint':name,'used':used,'limit':rhs,
                                'remaining':max(0.,rhs-used),'binding':abs(used-rhs)<1e-5})
    note=('Service target enforced and met under synthetic model assumptions.' if feasible else
          f'Service target NOT met: best economic plan reaches {service:.1%} vs required {min_service:.1%}. Escalate or relax constraints.')
    return Plan('Optimized' if feasible else 'Service target unmet',
        pd.DataFrame(allocation_rows),base,total_cost,margin_remaining,service,
        base_service,float((base.at_risk_units*base.unit_margin).sum())-margin_remaining,
        feasible,note,pd.DataFrame(constraint_rows))


def sensitivity(event_node,days,demand_factor,budget,min_service):
    rows=[]
    for cap in [0.5,0.75,1.,1.25,1.5]:
        p=plan_recovery(event_node,days,demand_factor,budget,min_service,supplier_capacity_factor=cap)
        rows.append({'supplier_capacity':f'{cap:.0%}','service_level':p.service_level,
                     'response_cost':p.total_cost,'remaining_margin_exposure':p.margin_remaining,
                     'meets_service_target':p.feasible})
    return pd.DataFrame(rows)
