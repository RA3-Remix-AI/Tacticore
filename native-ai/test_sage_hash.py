import unittest
from sage_hash import sage_hash

class AssetIdentifierHash(unittest.TestCase):
    def test_known_game_identifiers_and_literal_form(self):
        for name,expected in (('AlliedBarracks',0x509bd329),('AlliedRefinery',0x8ece261c),
            ('AlliedAirfield',0x5b3008b7),('AlliedPowerPlant',0x89b86e3d),('AlliedMCV',0x28da574e),
            ('CelestialDF41',0x25241ce6),('AlliedAntiNavyShipTech3',0x9356389f)):
            self.assertEqual(sage_hash(name.lower()),expected)
        self.assertEqual(sage_hash(''),0)
        self.assertEqual(sage_hash('0x799613e0'),0x799613e0)

if __name__=='__main__':unittest.main()
