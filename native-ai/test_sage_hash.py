import unittest
from sage_hash import sage_hash


class AssetIdentifierHash(unittest.TestCase):
    def test_known_game_identifiers_and_literal_form(self):
        for name, expected in (
            ("AlliedBarracks", 0x509BD329),
            ("AlliedRefinery", 0x8ECE261C),
            ("AlliedAirfield", 0x5B3008B7),
            ("AlliedPowerPlant", 0x89B86E3D),
            ("AlliedMCV", 0x28DA574E),
            ("CelestialDF41", 0x25241CE6),
            ("AlliedAntiNavyShipTech3", 0x9356389F),
        ):
            self.assertEqual(sage_hash(name.lower()), expected)
        self.assertEqual(sage_hash(""), 0)
        self.assertEqual(sage_hash("0x799613e0"), 0x799613E0)


if __name__ == "__main__":
    unittest.main()
