import json
from datetime import datetime,timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import networkx as nx
from engine.core import NODES,EVENTS,graph,affected_nodes,exposure,options,recommendation,explain
from engine.optimizer import BOM,SOURCES,plan_recovery,sensitivity

st.set_page_config(page_title='Supply Chain Decision Intelligence | POC',page_icon='🔗',layout='wide')
st.title('🔗 Supply Chain Decision Intelligence · V2')
st.caption('Disruption → Dependencies → Exposure → Scenario Comparison → Explainable Recommendation → Human Approval')
st.warning('**Portfolio demonstration:** All suppliers, customers, inventory, demand, costs and disruptions are synthetic. Recommendations are deterministic scenario calculations, not production AI or validated operational forecasts.',icon='🧪')

with st.sidebar:
 st.header('1 · Disruption event')
 event=st.selectbox('Choose an event',list(EVENTS))
 info=EVENTS[event]
 days=st.slider('Disruption duration (days)',1,30,info['days'])
 demand=st.slider('Demand change (%)',-30,60,0,5)
 st.header('2 · Decision constraints')
 budget=st.slider('Maximum response budget ($)',0,500000,250000,10000)
 service=st.slider('Minimum required service level (%)',60,100,85,1)/100
 st.caption('Changing any input recalculates the impact and options.')
 st.header('3 · V2 capacity assumptions')
 supplier_capacity=st.slider('Alternate supplier capacity (%)',50,150,100,5)/100
 transport_capacity=st.slider('Transport capacity (%)',50,150,100,5)/100
 extra_delay=st.slider('Additional response delay (days)',0,7,0)

factor=1+demand/100
impacted=affected_nodes(info['node'])
opts,exp=options(info['node'],days,factor,budget,service)
rec=recommendation(opts)
optimized=plan_recovery(info['node'],days,factor,budget,service,supplier_capacity,transport_capacity,extra_delay)
labels={node:label for node,_,label in NODES}

pages=st.tabs(['🚨 Event & KPIs','🕸️ Dependency Graph','📉 Business Impact','⚖️ Response Scenarios','🧠 Decision Explanation','✅ Governance & Audit','📚 Model Notes','🧩 BOM & Capacity','🧮 Recovery Optimizer','📊 Sensitivity Analysis'])
with pages[0]:
 st.subheader(event)
 st.write(info['description'])
 total_rev=float(exp.revenue_exposure.sum()) if not exp.empty else 0
 total_margin=float(exp.margin_exposure.sum()) if not exp.empty else 0
 a,b,c,d=st.columns(4)
 a.metric('Impacted graph entities',len(impacted))
 b.metric('Affected products',len(exp))
 c.metric('Revenue exposure',f'${total_rev:,.0f}')
 d.metric('Margin exposure',f'${total_margin:,.0f}')
 st.info('Revenue and margin exposure are modeled amounts tied to uncovered demand during the disruption, **not** verified losses or probabilistic estimates.')
with pages[1]:
 st.subheader('Cascading dependencies')
 g=graph()
 # Fixed layered layout keeps the diagram stable across reruns.
 level={'Port':0,'Tier 2':1,'Tier 1':2,'Component':3,'Plant':4,'Product':5,'Customer':6}
 levels={}
 for n,attrs in g.nodes(data=True): levels.setdefault(level[attrs['kind']],[]).append(n)
 fig=go.Figure()
 pos={}
 for x,nodes in levels.items():
  for i,n in enumerate(nodes):pos[n]=(x,(i-(len(nodes)-1)/2)*1.6)
 for u,v in g.edges():
  fig.add_trace(go.Scatter(x=[pos[u][0],pos[v][0]],y=[pos[u][1],pos[v][1]],mode='lines',line=dict(color='#e58f39' if u in impacted and v in impacted else '#aeb6c2',width=2),hoverinfo='skip',showlegend=False))
 for active,color,name in [(False,'#aeb6c2','Unaffected'),(True,'#e46b38','Affected')]:
  ns=[n for n in g.nodes if (n in impacted)==active]
  fig.add_trace(go.Scatter(x=[pos[n][0] for n in ns],y=[pos[n][1] for n in ns],mode='markers+text',text=[g.nodes[n]['label'] for n in ns],textposition='top center',marker=dict(size=19,color=color),name=name,hovertext=[f"{n} · {g.nodes[n]['kind']}" for n in ns],hoverinfo='text'))
 fig.update_layout(height=520,margin=dict(l=10,r=10,t=40,b=20),xaxis=dict(visible=False),yaxis=dict(visible=False),legend=dict(orientation='h'))
 st.plotly_chart(fig,use_container_width=True)
 st.caption('Orange = reachable downstream dependencies from the selected event. The alternate supplier is shown as a potential response asset, not as an automatically affected dependency.')
with pages[2]:
 st.subheader('Estimated operational exposure')
 if exp.empty:st.info('No affected product demand in this modeled network.')
 else:
  show=exp.copy()
  show['product']=show['product'].map(labels)
  show['customer']=show['customer'].map(labels)
  st.dataframe(show[['product','customer','daily_demand','inventory_units','coverage_days','shortfall_days','at_risk_units','revenue_exposure','margin_exposure']].round(1),use_container_width=True,hide_index=True)
  st.bar_chart(show.set_index('product')[['revenue_exposure','margin_exposure']])
  st.caption('Assumes no inbound replenishment during the disruption and one component per finished unit. Values represent exposure under those assumptions.')
with pages[3]:
 st.subheader('Constrained response comparison')
 if opts.empty:st.info('No response scenarios apply.')
 else:
  table=opts[['option','incremental_cost','response_lead_days','service_level','remaining_margin_exposure','estimated_total_cost','feasible']].copy()
  table['service_level']=table.service_level.map(lambda x:f'{x:.1%}')
  st.dataframe(table,use_container_width=True,hide_index=True)
  st.caption('Feasible = within response budget, meets minimum modeled service level, and response lead time is within disruption duration. Ranking minimizes response spend + remaining margin exposure.')
  st.bar_chart(opts.set_index('option')[['incremental_cost','remaining_margin_exposure']])
  if rec:st.success(f"Lowest modeled feasible cost: {rec['option']}")
  else:st.error('No modeled response meets all constraints. Adjust constraints or escalate.')
with pages[4]:
 st.subheader('Explainable recommendation')
 st.markdown(explain(rec,exp))
 st.markdown('**Decision trace**')
 st.write(f"Event: {event} · Duration: {days} days · Demand multiplier: {factor:.2f}×")
 st.write(f"Constraints: response budget ≤ ${budget:,.0f}, minimum service {service:.0%}")
 if rec:
  st.write(f"Selection rule: minimize total modeled economic cost across {int(opts.feasible.sum())} feasible response(s).")
  st.write(f"Assumption for selected option: {rec['assumptions']}")
 st.caption('This is grounded, template-based explanation—not an LLM-generated claim or autonomous agent.')
with pages[5]:
 st.subheader('Human-in-the-loop decision')
 if 'audit' not in st.session_state:st.session_state.audit=[]
 if rec:
  st.write(f"Proposed: **{rec['option']}**")
  reviewer=st.text_input('Reviewer / role',placeholder='Supply Chain Program Manager')
  rationale=st.text_area('Decision rationale',placeholder='Explain why the proposed response is acceptable or requires changes')
  left,right=st.columns(2)
  def log_decision(action):
   st.session_state.audit.append({'timestamp_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'event':event,'duration_days':days,'demand_change_pct':demand,'budget_usd':budget,'minimum_service':service,'recommended_option':rec['option'],'action':action,'reviewer':reviewer.strip(),'rationale':rationale.strip()})
  valid=bool(reviewer.strip() and rationale.strip())
  with left:
   if st.button('Approve recommendation',disabled=not valid,use_container_width=True):log_decision('APPROVED');st.success('Approval recorded in session audit log. No external system was changed.')
  with right:
   if st.button('Reject / request revision',disabled=not valid,use_container_width=True):log_decision('REJECTED');st.info('Rejection recorded in session audit log.')
  if not valid:st.caption('Enter reviewer and rationale to enable a decision.')
 else:st.info('No feasible recommendation to approve. Adjust constraints or escalate.')
 st.markdown('**Session audit trail**')
 if st.session_state.audit:
  st.dataframe(pd.DataFrame(st.session_state.audit),hide_index=True,use_container_width=True)
  st.download_button('Download audit JSON',json.dumps(st.session_state.audit,indent=2),file_name='decision_audit.json',mime='application/json')
 else:st.caption('No decisions recorded yet. This session-only log resets on app restart.')
with pages[6]:
 st.subheader('What this POC proves—and what it does not')
 st.markdown('''**Implemented:** deterministic event propagation through a directed dependency graph; inventory coverage and economic exposure calculations; transparent response scenarios; budget/service constraints; cost-based recommendation; approval/rejection with session audit export.

**V2 adds:** product-component BOM visibility, supplier/route capacities, qualified recovery sources, lead-time constraints, linear-programming recovery allocations, budget-limited optimization and sensitivity analysis.\n\n**Not implemented:** real ERP/WMS/TMS integration; verified multi-tier supplier discovery; dynamic shipment ETAs; supplier qualification workflow; constrained transport network optimization; probabilistic event modeling; true operational digital twin; external AI/LLM; persistent enterprise audit; automatic procurement execution.

**Model limitations:** response recovery percentages and costs are illustrative assumptions. Service level is calculated against affected-product demand during the disruption. Revenue exposure is not booked revenue loss. Reallocation ignores donor-network impacts. Use for demonstrations, not real procurement decisions.''')

with pages[7]:
 st.subheader('V2 · Bill of materials and operational capacity')
 st.caption('BOM links products to components. Only High-criticality bottleneck components drive V2 recovery; secondary BOM lines are shown for visibility but not independently optimized.')
 st.markdown('**Product-to-component BOM**')
 st.dataframe(BOM.assign(product=BOM['product'].map(labels),component=BOM['component'].map(labels)),hide_index=True,use_container_width=True)
 st.markdown('**Qualified recovery sources and transport lanes**')
 st.dataframe(SOURCES,hide_index=True,use_container_width=True)
 st.info('Capacity is shared across eligible products. Transfer capacity is already net of protected donor stock; lead times and route limits constrain recovery. All values are synthetic.')
with pages[8]:
 st.subheader('V2 · Capacity-aware recovery optimization')
 a,b,c,d=st.columns(4)
 a.metric('Baseline service',f'{optimized.baseline_service:.1%}')
 b.metric('Optimized service',f'{optimized.service_level:.1%}',delta=f'{(optimized.service_level-optimized.baseline_service)*100:.1f} pp')
 c.metric('Response spend',f'${optimized.total_cost:,.0f}')
 d.metric('Remaining margin exposure',f'${optimized.margin_remaining:,.0f}')
 if optimized.feasible:st.success(optimized.note)
 else:st.error(optimized.note)
 st.markdown('**Recommended allocation by source and product**')
 if optimized.allocations.empty:st.info('No economically beneficial eligible recovery allocations under current constraints.')
 else:
  display=optimized.allocations.copy()
  display['product']=display['product'].map(labels)
  st.dataframe(display[['source','product','component','kind','route','lead_days','recovered_product_units','component_units','incremental_cost','avoided_margin']].round(1),hide_index=True,use_container_width=True)
  st.bar_chart(display.groupby('source')[['recovered_product_units']].sum())
 st.markdown('**Residual exposure by product**')
 shown=optimized.product_impact.copy()
 shown['product']=shown['product'].map(labels)
 st.dataframe(shown[['product','horizon_demand','at_risk_units','recovered_units','remaining_units','remaining_margin']].round(1),hide_index=True,use_container_width=True)
 st.markdown('**Constraint utilization**')
 if not optimized.constraints.empty:
  st.dataframe(optimized.constraints.round(2),hide_index=True,use_container_width=True)
  binding=optimized.constraints[optimized.constraints.binding]
  st.caption('Binding constraints: '+(', '.join(binding.constraint.tolist()) if not binding.empty else 'None'))
 st.caption('Linear programming minimizes response spend + uncovered contribution margin. The minimum service level is a hard solver constraint when feasible; if infeasible, a diagnostic maximum-recovery plan is shown and flagged as NOT meeting the target. This is a simplified component recovery model, not an ERP-grade production scheduler.')
with pages[9]:
 st.subheader('V2 · Supplier capacity sensitivity')
 st.write('How does changing alternate supplier capacity affect service and spend, holding other inputs fixed?')
 sens=sensitivity(info['node'],days,factor,budget,service)
 st.dataframe(sens.assign(service_level=sens.service_level.map(lambda v:f'{v:.1%}')),hide_index=True,use_container_width=True)
 st.line_chart(sens.set_index('supplier_capacity')[['service_level']])
 st.caption('Sensitivity runs vary supplier capacity from 50% to 150% of synthetic baseline; transport capacity uses baseline in this chart. This is deterministic what-if analysis, not probabilistic forecasting.')
