"""Pure projection fixtures; no field capability or live-game claims."""
import copy
import unittest

from host_runtime.selector import SelectionProfile, select_target


def contact(identity="a", **changes):
    row = dict(contact_id=identity, object_id=100 if identity=="a" else 101,
               owner_player_id=4, relation="enemy", currently_visible=True,
               observed_frame=100, xyz=[600,0,0], hp=1000, role="structure",
               type_hash="0x123", template="SovietBarracks")
    row.update(changes)
    return row


class SelectorTests(unittest.TestCase):
    def pick(self, rows, **kwargs):
        return select_target(rows, [[0,0,0]], game_frame=100, own_view_verified=True, **kwargs)

    def test_all_rejected_candidates_have_explicit_reasons(self):
        rows=[contact("near",xyz=[1,0,0]),contact("hidden",currently_visible=False),
              contact("old",observed_frame=1),contact("dead",hp=0),
              contact("friend",relation="ally"),contact("wall",template="SovietWall")]
        out=self.pick(rows)
        self.assertIsNone(out.selected)
        self.assertEqual(len(out.diagnostics),len(rows))
        self.assertEqual(set(out.rejection_counts),{"target_too_near","not_currently_visible","observation_expired","not_alive","not_enemy","forbidden_template"})
        self.assertIsNone(out.diagnostics[1]["distance"])
        self.assertIsNone(out.diagnostics[2]["distance"])

    def test_empty_unverified_and_bad_anchors_never_propose(self):
        self.assertEqual(self.pick([]).rejection_counts,{"no_contacts":1})
        out=select_target([contact()],[[0,0,0]],game_frame=100,own_view_verified=False)
        self.assertEqual(out.reason_code,"own_view_unverified")
        self.assertIsNone(out.selected)
        out=select_target([contact()],[],game_frame=100,own_view_verified=True)
        self.assertEqual(out.reason_code,"invalid_anchors")

    def test_ranking_stable_and_inputs_unchanged(self):
        rows=[contact("b"),contact("a")];before=copy.deepcopy(rows)
        self.assertEqual(self.pick(rows).selected["contact_id"],"a")
        self.assertEqual(self.pick(list(reversed(rows))).selected["contact_id"],"a")
        self.assertEqual(rows,before)
        self.assertFalse(self.pick(rows).authority_granted)

    def test_hidden_threat_does_not_influence_ranking(self):
        near=contact("a",xyz=[600,0,0]);far=contact("b",xyz=[800,0,0])
        threat=contact("tank",object_id=102,xyz=[600,0,0],role="armor",currently_visible=False)
        self.assertEqual(self.pick([near,far,threat]).selected["contact_id"],"a")
        threat["currently_visible"]=True
        far["xyz"]=[960,0,0]
        self.assertEqual(self.pick([near,far,threat]).selected["contact_id"],"b")

    def test_duplicate_identity_and_future_nan_rows_rejected(self):
        self.assertEqual(self.pick([contact(),contact()]).rejection_counts,{"duplicate_contact_id":2})
        self.assertIsNone(self.pick([contact(observed_frame=101)]).selected)
        self.assertIsNone(self.pick([contact(xyz=[float("nan"),0,0])]).selected)

    def test_profile_separates_near_field_experiment(self):
        row=contact(xyz=[50,0,0],hp=100)
        self.assertIsNone(self.pick([row]).selected)
        out=self.pick([row],profile=SelectionProfile(name="near_fixture",min_distance=0,max_distance=100,min_hp=1))
        self.assertIsNotNone(out.selected)
        self.assertEqual(out.profile,"near_fixture")
        self.assertFalse(out.authority_granted)


if __name__=="__main__":unittest.main()
