import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "merge_unused_files.py"


def write_csv(csv_file: Path, paths: list[Path]) -> None:
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    with csv_file.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Path"])
        writer.writeheader()
        writer.writerows({"Path": str(path)} for path in paths)


def read_paths(path_file: Path) -> list[Path]:
    return [
        Path(line)
        for line in path_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class MergeUnusedFilesTests(unittest.TestCase):
    def run_tool(
        self,
        csv_file: Path,
        source_dir: Path,
        *,
        input_root: Path | None = None,
        merge_target: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(SCRIPT),
            str(csv_file),
            "--missing-in",
            str(source_dir),
        ]
        if input_root:
            command.extend(["--input-root", str(input_root)])
        if merge_target:
            command.extend(["--merge-result-to", str(merge_target)])

        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_compares_paths_relative_to_different_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            logged_root = root / "logged-root"
            source.mkdir()
            (source / "dbf.unity3d").write_bytes(b"used")
            (source / "really_missing.unity3d").write_bytes(b"unused")

            csv_file = root / "outputs" / "Logfile.CSV"
            write_csv(csv_file, [logged_root / "dbf.unity3d"])

            self.run_tool(csv_file, source, input_root=logged_root)

            unused_paths = read_paths(csv_file.parent / "unused_original_files.txt")
            self.assertEqual(unused_paths, [source / "really_missing.unity3d"])

    def test_used_paths_persist_after_csv_is_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            source.mkdir()
            first = source / "first.bin"
            second = source / "second.bin"
            unused = source / "unused.bin"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            unused.write_bytes(b"unused")

            csv_file = root / "outputs" / "Logfile.CSV"
            write_csv(csv_file, [first])
            self.run_tool(csv_file, source)

            write_csv(csv_file, [second])
            self.run_tool(csv_file, source)

            csv_file.unlink()
            self.run_tool(csv_file, source)

            used_paths = set(read_paths(csv_file.parent / "used_original_files.txt"))
            unused_paths = read_paths(csv_file.parent / "unused_original_files.txt")
            self.assertEqual(used_paths, {first, second})
            self.assertEqual(unused_paths, [unused])

    def test_merge_restores_file_when_it_becomes_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            target = root / "merged"
            source.mkdir()
            always_used = source / "always-used.bin"
            newly_used = source / "newly-used.bin"
            always_used.write_bytes(b"original-a")
            newly_used.write_bytes(b"original-b")

            csv_file = root / "outputs" / "Logfile.CSV"
            write_csv(csv_file, [always_used])
            self.run_tool(csv_file, source, merge_target=target)
            self.assertEqual((target / newly_used.name).stat().st_size, 0)

            write_csv(csv_file, [newly_used])
            self.run_tool(csv_file, source, merge_target=target)

            self.assertEqual(
                (target / newly_used.name).read_bytes(),
                newly_used.read_bytes(),
            )
            self.assertEqual(
                read_paths(csv_file.parent / "unused_original_files.txt"),
                [],
            )


if __name__ == "__main__":
    unittest.main()
