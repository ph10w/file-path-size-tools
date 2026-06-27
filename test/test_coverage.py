import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COVERAGE_CONFIG = PROJECT_ROOT / ".coveragerc"


class CoverageTests(unittest.TestCase):
    def test_main_program_reaches_minimum_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            environment = os.environ.copy()
            environment["COVERAGE_FILE"] = str(Path(temp_dir) / ".coverage")

            commands = [
                [
                    sys.executable,
                    "-m",
                    "coverage",
                    "run",
                    "--rcfile",
                    str(COVERAGE_CONFIG),
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "test",
                    "-p",
                    "test_merge_unused_files.py",
                    "-v",
                ],
                [
                    sys.executable,
                    "-m",
                    "coverage",
                    "combine",
                    "--rcfile",
                    str(COVERAGE_CONFIG),
                ],
                [
                    sys.executable,
                    "-m",
                    "coverage",
                    "report",
                    "--rcfile",
                    str(COVERAGE_CONFIG),
                ],
            ]

            results = []
            for command in commands:
                result = subprocess.run(
                    command,
                    cwd=PROJECT_ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                results.append(result)
                if result.returncode != 0:
                    output = "\n".join(
                        part.strip()
                        for part in (result.stdout, result.stderr)
                        if part.strip()
                    )
                    self.fail(
                        "Coverage-Messung fehlgeschlagen. "
                        "Installiere zuerst requirements-dev.txt.\n"
                        f"{output}"
                    )

            print("\n" + results[-1].stdout.strip())


if __name__ == "__main__":
    unittest.main()
