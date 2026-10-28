"""The isolated transport changes observation only, never native commands."""
import ast
from pathlib import Path
import unittest


class AreaDefenseTransportTests(unittest.TestCase):
    def test_only_observer_import_verification_and_provenance_differ(self):
        root=Path(__file__).resolve().parent
        base=(root/'macro-policy-runtime/client.py').read_text(encoding='utf-8')
        expected=base.replace('from macro_observation import MacroObserver',
            'from macro_area_defense_observation import MacroObserver\nfrom verify_area_defense_observer import verify as verify_observer_extension')
        expected=expected.replace('        verify_session_package(self.session)',
            '        verify_observer_extension()\n        verify_session_package(self.session)')
        expected=expected.replace("'build.py','client.py']", "'build.py','client_area_defense.py']")
        expected=expected.replace("ROOT/'native-ai/macro_observation.py',",
            "ROOT/'native-ai/macro_observation.py',ROOT/'native-ai/macro_area_defense_observation.py',ROOT/'native-ai/verify_area_defense_observer.py',")
        actual=(root/'macro-policy-runtime/client_area_defense.py').read_text(encoding='utf-8')
        self.assertEqual(ast.dump(ast.parse(expected)),ast.dump(ast.parse(actual)))


if __name__=='__main__':unittest.main()
