"""Exercise the real read-only projection against the Agent's public contract.

All proof/observation data here is synthetic. No native reader is imported.
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

from battle_agent import BattleAgent
from engine import ContractError,Snapshot,StrategyEngine
from fixtures import SESSION,binding
from tactical_fixtures import tactical_snapshot


path=Path(__file__).resolve().parents[1]/"visibility/projection.py"
spec=importlib.util.spec_from_file_location("_projection_contract_fixture",path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class ProjectionBoundary(unittest.TestCase):
    def setUp(self):
        self.sha="a"*64
        self.proof=dict(schema_version=2,object_visibility_method="native_footprint_reconstruction",footprint_live_verified=True,session_id=SESSION,target_player_id=3,package_sha256=self.sha,terrain_view_live_verified=True,object_view_live_verified=True,conservative_stealth_exclusion_reviewed=True,no_observer_fallback=True)
        self.safety={"package_sha256":self.sha,"templates":{"0x123":{"role":"infantry","source_audited_no_intrinsic_stealth":True}}}
        self.observation=dict(relation="enemy",terrain_shroud=1,object_shroud_cached=1,object_shroud_reconstructed=1,object_visibility_method="native_footprint_reconstruction",runtime_stealth_safe=True,type_hash="0x123",object_id=42,owner_player_id=4,region_id="region_1_1",identity_stable=True,observer_fallback=False,alive=True,address="0x12345678",hp=100,xyz=[999,888,0])
        self.projector=module.VisibilityProjection(SESSION,3,self.sha,self.proof,self.safety,ttl_seconds=90)

    def snapshot(self,extension,ident,at):
        raw=tactical_snapshot(ident,at);raw["battlefield"]=extension
        # Last-seen regions remain known; they need no current enemy descriptor.
        ids={*raw["capabilities"]["regions"],*(r["region_id"] for r in extension["regions"]),*(c["region_id"] for c in extension["contacts"])}
        raw["capabilities"]["regions"]=sorted(ids)
        return raw

    def test_actual_projection_crosses_contract_without_hidden_native_fields(self):
        extension=self.projector.project([self.observation],100)
        raw=self.snapshot(extension,1,100);Snapshot.from_dict(raw)
        agent=BattleAgent(StrategyEngine(binding()));agent.observe(raw)
        context=agent.context(agent.latest.model_context(binding()))
        text=json.dumps(context)
        for forbidden in ["0x12345678","0x123",'"object_id"','"xyz"','"hp"']:self.assertNotIn(forbidden,text)
        self.assertEqual(context["working_memory"]["battlefield"]["viewer_player_id"],3)
        self.assertTrue(context["working_memory"]["battlefield"]["contacts"][0]["currently_visible"])

    def test_actual_projection_fog_keeps_old_fact_but_not_current_regions_or_attack_handle(self):
        first=self.projector.project([self.observation],100)
        agent=BattleAgent(StrategyEngine(binding()));agent.observe(self.snapshot(first,1,100))
        hidden=copy.deepcopy(self.observation);hidden.update(terrain_shroud=0,region_id="region_9_9",xyz=[99999,88888,0],hp=0,alive=False)
        second=self.projector.project([hidden],105)
        self.assertTrue(all(not region["currently_visible"] and region["role_counts"]=={} and region["observed_at_game_seconds"]==100 for region in second["regions"]))
        self.assertEqual(second["contacts"][0]["region_id"],"region_1_1")
        agent.observe(self.snapshot(second,2,105))
        self.assertFalse(next(iter(agent.contact_facts.values()))["currently_visible"])
        # Projection TTL90 can safely exceed Agent TTL60: old facts are ignored,
        # not upgraded, and no hidden destruction notification is fabricated.
        third=self.projector.project([],161);agent.observe(self.snapshot(third,3,161))
        self.assertEqual(agent.contact_facts,{})
        self.assertNotIn("region_9_9",json.dumps(agent.public_memory()))

    def test_actual_observer_projection_is_rejected_by_computer_snapshot_binding(self):
        proof=copy.deepcopy(self.proof);proof["target_player_id"]=2
        observer=module.VisibilityProjection(SESSION,2,self.sha,proof,self.safety)
        extension=observer.project([self.observation],100)
        self.assertTrue(extension["visibility_verified"])
        with self.assertRaisesRegex(ContractError,"battlefield_viewer_mismatch"):Snapshot.from_dict(self.snapshot(extension,1,100))

    def test_known_stale_object_cache_alone_does_not_admit_enemy(self):
        old=copy.deepcopy(self.observation);old.pop("object_shroud_reconstructed");old.pop("object_visibility_method")
        extension=self.projector.project([old],100)
        self.assertEqual(extension["contacts"],[])
        self.assertEqual(extension["regions"],[])

    def test_old_cache_proof_cannot_authorize_new_footprint_projection(self):
        for key in ["schema_version","object_visibility_method","footprint_live_verified"]:
            proof=copy.deepcopy(self.proof);proof.pop(key)
            projector=module.VisibilityProjection(SESSION,3,self.sha,proof,self.safety)
            with self.subTest(missing=key):
                output=projector.project([self.observation],100)
                self.assertFalse(output["visibility_verified"]);self.assertEqual(output["contacts"],[])


if __name__=="__main__":unittest.main(verbosity=2)
