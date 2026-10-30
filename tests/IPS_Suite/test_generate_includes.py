"""Regression tests for generated suite control categories."""
import importlib.util
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "generate_ips_suite_includes", ROOT / "validation" / "generate_ips_suite_includes.py"
)
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class GeneratedCategoriesTests(unittest.TestCase):
    def test_categories_are_assigned_after_uniform_renaming(self):
        source = (
            'uniform float Contrast < ui_category = "Old Contrast"; > = 1.0;\n'
            'float result = Contrast;\n'
        )
        self.assertEqual(
            generator.rename_uniforms(source, "Contrast", "1. Contrast"),
            'uniform float ContrastContrast < ui_category = "1. Contrast"; > = 1.0;\n'
            'float result = ContrastContrast;\n',
        )

    def test_all_generated_controls_use_their_suite_category(self):
        for build, expected in (
            (generator.contrast, "1. Contrast"),
            (generator.deband, "2. Debanding"),
            (generator.clarity, "3. Clarity"),
        ):
            with self.subTest(category=expected):
                controls = re.findall(r"\buniform\s+\w+\s+\w+\s*<([^>]*)>", build())
                self.assertTrue(controls)
                for control in controls:
                    self.assertEqual(re.findall(r'ui_category = "([^"]+)"', control), [expected])


if __name__ == "__main__":
    unittest.main()
