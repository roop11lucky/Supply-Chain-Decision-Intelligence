import unittest
from engine.core import graph,affected_nodes,exposure,options,recommendation
class DecisionEngineTests(unittest.TestCase):
 def test_graph(self):
  self.assertIn('CUST_A',affected_nodes('PORT_SZ'))
  self.assertNotIn('SUP_ALT',affected_nodes('PORT_SZ'))
 def test_exposure(self):
  x=exposure('PORT_SZ',14)
  self.assertEqual(len(x),2)
  p20=x.set_index('product').loc['PROD_P20']
  self.assertAlmostEqual(p20.coverage_days,6)
  self.assertAlmostEqual(p20.at_risk_units,1440)
 def test_zero_disruption(self):
  self.assertAlmostEqual(exposure('SUP_T1',0).at_risk_units.sum(),0)
 def test_options(self):
  o,e=options('PORT_SZ',14,1,250000,.85)
  self.assertEqual(len(o),5)
  r=recommendation(o)
  self.assertIsNotNone(r)
  self.assertTrue(r['feasible'])
 def test_infeasible(self):
  o,_=options('PORT_SZ',14,1,0,1.0)
  self.assertIsNone(recommendation(o))
if __name__=='__main__':unittest.main()
