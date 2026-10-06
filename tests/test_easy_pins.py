import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "数字组合.py"
SPEC = importlib.util.spec_from_file_location("easy_pins", SCRIPT_PATH)
easy_pins = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(easy_pins)


class EasyPinsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output = Path(self.temp_dir.name) / "easy_pins.txt"
        self.history = self.output.with_name("easy_pins_history.txt")

    def generate(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            domains = easy_pins.generate_100_easy_pins(self.output)
        self.assertEqual(stdout.getvalue().splitlines(), domains)
        self.assertEqual(self.output.read_text(encoding="utf-8").splitlines(), domains)
        self.assertEqual(len(domains), 100)
        self.assertEqual(len(set(domains)), 100)
        for domain in domains:
            self.assertRegex(domain, r"\A[0-9]{6}\.xyz\Z")
        pins = {domain.removesuffix(".xyz") for domain in domains}
        self.assertTrue(pins <= easy_pins.build_easy_pins_pool())
        return pins

    def test_repeated_batches_are_disjoint(self):
        used = set()
        for _ in range(5):
            pins = self.generate()
            self.assertTrue(used.isdisjoint(pins))
            used.update(pins)
        self.assertEqual(easy_pins.read_generated_pins(self.history), used)

    def test_existing_output_is_migrated_with_leading_zeros(self):
        old_pins = {"001001", "012012", "024680"}
        self.output.write_text("\n".join(sorted(old_pins)) + "\n", encoding="utf-8-sig")
        pins = self.generate()
        self.assertTrue(old_pins.isdisjoint(pins))
        self.assertEqual(easy_pins.read_generated_pins(self.history), old_pins | pins)

    def test_history_survives_missing_output(self):
        first = self.generate()
        self.output.unlink()
        second = self.generate()
        self.assertTrue(first.isdisjoint(second))

    def test_mixed_numeric_and_domain_records_are_excluded(self):
        self.history.write_text("001001\n012012.xyz\n", encoding="utf-8")
        self.output.write_text("001001.xyz\n024680.XYZ\n", encoding="utf-8")
        old_pins = {"001001", "012012", "024680"}
        pins = self.generate()
        self.assertTrue(old_pins.isdisjoint(pins))
        self.assertEqual(easy_pins.read_generated_pins(self.history), old_pins | pins)

    def test_other_suffixes_and_malformed_domains_are_rejected(self):
        for record in ("001001.com", "001001.xyz.xyz", "00101.xyz", "0010010.xyz"):
            with self.subTest(record=record):
                self.output.write_text(record + "\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    easy_pins.read_generated_pins(self.output)

    def test_exactly_one_batch_left_then_exhaustion(self):
        pool = sorted(easy_pins.build_easy_pins_pool())
        easy_pins.save_pins(self.history, pool[100:])
        self.assertEqual(self.generate(), set(pool[:100]))
        self.assertIn("001001.xyz", self.output.read_text(encoding="utf-8").splitlines())
        original_output = self.output.read_bytes()
        original_history = self.history.read_bytes()
        with self.assertRaises(ValueError):
            self.generate()
        self.assertEqual(self.output.read_bytes(), original_output)
        self.assertEqual(self.history.read_bytes(), original_history)

    def test_insufficient_batch_preserves_files(self):
        pool = sorted(easy_pins.build_easy_pins_pool())
        easy_pins.save_pins(self.history, pool[:-99])
        self.output.write_text(pool[0] + "\n", encoding="utf-8")
        original_output = self.output.read_bytes()
        original_history = self.history.read_bytes()
        with self.assertRaises(ValueError):
            self.generate()
        self.assertEqual(self.output.read_bytes(), original_output)
        self.assertEqual(self.history.read_bytes(), original_history)

    def test_invalid_history_is_not_overwritten(self):
        original = "001001\ninvalid\n"
        self.history.write_text(original, encoding="utf-8")
        with self.assertRaises(ValueError):
            self.generate()
        self.assertEqual(self.history.read_text(encoding="utf-8"), original)
        self.assertFalse(self.output.exists())

    def test_failed_replace_preserves_history_and_cleans_temp_file(self):
        self.history.write_text("001001\n", encoding="utf-8")
        with patch.object(Path, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                self.generate()
        self.assertEqual(self.history.read_text(encoding="utf-8"), "001001\n")
        self.assertEqual(list(self.output.parent.iterdir()), [self.history])

    def test_separate_processes_do_not_repeat(self):
        batches = []
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT_PATH)],
                cwd=self.temp_dir.name, capture_output=True, text=True, check=True,
            )
            domains = result.stdout.splitlines()
            self.assertEqual(len(domains), 100)
            self.assertEqual(len(set(domains)), 100)
            for domain in domains:
                self.assertRegex(domain, r"\A[0-9]{6}\.xyz\Z")
            batches.append({domain.removesuffix(".xyz") for domain in domains})
        self.assertTrue(batches[0].isdisjoint(batches[1]))
        self.assertEqual(easy_pins.read_generated_pins(self.history), set.union(*batches))


if __name__ == "__main__":
    unittest.main()
