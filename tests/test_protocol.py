import unittest
import json
from importlib.resources import files
from automower_ble.protocol import RestrictionReason


class TestProtocolClasses(unittest.TestCase):
    def setUp(self):
        with files("automower_ble").joinpath("protocol.json").open("r") as f:
            self.protocol = json.load(f)  # Load the parameters to have them available
            
    def test(self):
        x = 1
        xr = RestrictionReason(x)
        
        self.assertEqual(xr, RestrictionReason.WEEK_SCHEDULE)
        
        
if __name__ == "__main__":
    unittest.main()
