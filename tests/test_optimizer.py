import unittest
from engine.core import EVENTS
from engine.optimizer import plan_recovery, sensitivity, BOM, SOURCES

class OptimizerTests(unittest.TestCase):
    def setUp(self):self.node=EVENTS['Tier-2 material supplier outage']['node']
    def test_nonnegative_and_budget(self):
        p=plan_recovery(self.node,12,budget=250000)
        self.assertLessEqual(p.total_cost,250000.01)
        self.assertTrue((p.product_impact.remaining_units>=-1e-6).all())
        self.assertTrue((p.product_impact.recovered_units<=p.product_impact.at_risk_units+1e-6).all())
    def test_zero_budget(self):
        p=plan_recovery(self.node,12,budget=0)
        self.assertAlmostEqual(p.total_cost,0)
    def test_no_disruption_impact(self):
        p=plan_recovery('PORT_SG',12)
        self.assertAlmostEqual(p.service_level,1.)
    def test_supplier_capacity_sensitivity(self):
        low=plan_recovery(self.node,12,supplier_capacity_factor=.5)
        high=plan_recovery(self.node,12,supplier_capacity_factor=1.5)
        self.assertGreaterEqual(high.service_level+1e-8,low.service_level)
    def test_recovery_uses_components(self):
        p=plan_recovery(self.node,12)
        for _,r in p.allocations.iterrows():
            self.assertFalse(BOM[(BOM['product']==r['product'])&(BOM['component']==r['component'])].empty)
    def test_sensitivity(self):self.assertEqual(len(sensitivity(self.node,12,1.,250000,.85)),5)
if __name__=='__main__':unittest.main()
