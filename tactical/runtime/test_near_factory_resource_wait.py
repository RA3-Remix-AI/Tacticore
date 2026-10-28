"""No game is opened. Waiting cannot relax native reserve or dispatch a retry."""
import unittest
from tactical.runtime.qualify_near_factory import production_resource_readiness

class ResourceReadiness(unittest.TestCase):
    def test_current_cash_must_cover_original_floor_cost_debt_and_wait_buffer(self):
        factory={'queue_candidate':{'nodes':[dict(kind_raw=1,native_cost_plus_30=220,paid_accumulator_plus_68=20)]}}
        low=production_resource_readiness(dict(resource_available=True,display_sum=1784),factory)
        self.assertFalse(low['ready']);self.assertEqual((low['required'],low['reserve_floor'],low['liability']),(1785,1000,200))
        self.assertTrue(production_resource_readiness(dict(resource_available=True,display_sum=1785),factory)['ready'])
    def test_unreadable_or_incompatible_queues_cannot_start_production(self):
        player=dict(resource_available=True,display_sum=10000)
        for factory in [{},{'queue_candidate':{}},{'queue_candidate':{'nodes':[dict(kind_raw=2)]}},
            {'queue_candidate':{'nodes':[dict(kind_raw=1,native_cost_plus_30=85,paid_accumulator_plus_68=86)]}}]:
            self.assertIsNone(production_resource_readiness(player,factory))
        self.assertIsNone(production_resource_readiness(dict(resource_available=False),{'queue_candidate':{'nodes':[]}}))

if __name__=='__main__':unittest.main()
