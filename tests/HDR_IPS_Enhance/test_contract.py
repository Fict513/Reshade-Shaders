"""Initial contract test. Numerical/FX suites accompany the implementation."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class DeliverableContract(unittest.TestCase):
    def test_required_math_and_effect_exist(self):
        self.assertTrue((ROOT / 'Shaders/HDRIPS_Math.fxh').is_file(),
                        'Required scalar math include is absent')
        self.assertTrue((ROOT / 'Shaders/HDR_IPS_Enhance.fx').is_file(),
                        'Required effect is absent')

if __name__ == '__main__':
    unittest.main()
