import unittest
from engine.core import EVENTS, exposure
from engine.optimizer import plan_recovery
from engine.orchestration import plan_snapshot,record_decision,decision_brief

class TestV3(unittest.TestCase):
 def test_events(self):
  self.assertGreaterEqual(len(EVENTS),9)
  for event in EVENTS.values():
   self.assertIsNotNone(exposure(event['node'],event['days']))
 def test_fingerprint_stable_and_changes(self):
  p=plan_recovery('SUP_T2',12)
  a=plan_snapshot('Supplier outage',12,0,250000,.85,1,1,0,p)
  b=plan_snapshot('Supplier outage',12,0,250000,.85,1,1,0,p)
  c=plan_snapshot('Supplier outage',12,0,260000,.85,1,1,0,p)
  self.assertEqual(a['plan_id'],b['plan_id'])
  self.assertNotEqual(a['plan_id'],c['plan_id'])
 def test_approval_and_rejection(self):
  p=plan_recovery('SUP_T2',12)
  a=plan_snapshot('Supplier outage',12,0,250000,.85,1,1,0,p)
  self.assertEqual(record_decision(a,'APPROVED','Planner','Checked assumptions')['action'],'APPROVED')
  a['meets_service_target']=False
  with self.assertRaises(ValueError):record_decision(a,'APPROVED','Planner','Reason')
  self.assertEqual(record_decision(a,'REJECTED','Planner','Insufficient service')['action'],'REJECTED')
 def test_brief(self):
  p=plan_recovery('SUP_T2',12)
  a=plan_snapshot('Supplier outage',12,0,250000,.85,1,1,0,p)
  self.assertIn('modeled',decision_brief(a,p))
if __name__=='__main__':unittest.main()
