import copy
import json
from pathlib import Path
import unittest
from assess_macro_outcome import map_terminal,verify_static

ROOT=Path(__file__).resolve().parents[1]

def terminal(name):
    rows=[json.loads(l) for l in (ROOT/'reports'/name/'native-match-transitions.jsonl').read_text().splitlines()]
    return [r for r in rows if r.get('simulation_frame')][-1]

class NativeOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.people=json.loads((ROOT/'acceptance/runs/20261028-073337-macro-probe/battle-host/participants.json').read_text())
        self.win=terminal('macro-scout-77972-match-watch-20261028-v1')

    def test_verified_native_loop_mapping_distinguishes_actual_win_and_loss(self):
        self.assertEqual(map_terminal(self.win,self.people)['winner_player_index'],3)
        self.assertEqual(map_terminal(terminal('macro-desktop-74296-match-watch-20261028-v1'),self.people)['winner_player_index'],4)
        verify_static(Path('E:/RedRar3/Data/RA3_1.12.game'))

    def test_array_index_is_not_guessed_from_player_id_or_ui_row(self):
        broken=copy.deepcopy(self.win)
        for r in broken['victory_conditions']['participants']:r['manager_index']=1-r['manager_index']
        with self.assertRaises(ValueError):map_terminal(broken,self.people)

    def test_nonterminal_both_victories_and_disconnects_do_not_produce_winner(self):
        for change in ('nonterminal','both_victory','disconnected'):
            row=copy.deepcopy(self.win)
            if change=='nonterminal':
                for r in row['result_records']:r.update(victory_frame=0,defeat_frame=0,raw=[0]*8)
            elif change=='both_victory':
                r=row['result_records'][1];r.update(victory_frame=16756,defeat_frame=0);r['raw'][2:4]=[0,16756]
            else:row['result_records'][0]['disconnect_frame_candidate']=100
            with self.subTest(change=change),self.assertRaises(ValueError):map_terminal(row,self.people)

if __name__=='__main__':unittest.main()
