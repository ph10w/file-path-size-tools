#!/usr/bin/env python3
"""Find files missing from a CSV path list and build a merged result folder.

Usage:
    python merge_unused_files.py Logfile.CSV --missing-in C:\\Dateien
    python merge_unused_files.py Logfile.CSV --missing-in C:\\Dateien
        --merge-result-to C:\\Zusammengefuehrt
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

USED_ORIGINAL_FILES_NAME = "used_original_files.txt"
UNUSED_ORIGINAL_FILES_NAME = "unused_original_files.txt"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_RESET = "\033[0m"


class FileSystem:
    @staticmethod
    def is_file(path: Path) -> bool:
        return path.is_file()

    @staticmethod
    def is_directory(path: Path) -> bool:
        return path.is_dir()

    @staticmethod
    def exists(path: Path) -> bool:
        return path.exists()

    @classmethod
    def is_empty_file(cls, path: Path) -> bool:
        return cls.is_file(path) and cls.file_size(path) == 0

    @staticmethod
    def file_size(path: Path) -> int:
        return path.stat().st_size

    @classmethod
    def files_in(cls, directory: Path, recursive: bool) -> list[Path]:
        pattern = "**/*" if recursive else "*"
        return [path for path in directory.glob(pattern) if cls.is_file(path)]

    @staticmethod
    def read_text(path: Path) -> str:
        return path.read_text(encoding="utf-8")

    @staticmethod
    def open_csv(path: Path) -> TextIO:
        return path.open("r", encoding="utf-8-sig", newline="")

    @staticmethod
    def write_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    @staticmethod
    def create_empty_file(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")

    @staticmethod
    def remove_file(path: Path) -> None:
        path.unlink()

    @staticmethod
    def copy_file(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    @staticmethod
    def resolve(path: Path) -> Path:
        return path.resolve()

    @staticmethod
    def resolved_relative_path(path: Path, root: Path) -> Path:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False))

    @staticmethod
    def relative_path(path: Path, root: Path) -> Path:
        return path.relative_to(root)

    @classmethod
    def is_same_or_within(cls, path: Path, directory: Path) -> bool:
        try:
            cls.relative_path(path, directory)
        except ValueError:
            return False
        return True


FILE_SYSTEM = FileSystem()


def resolve_listed_path(raw_path: str, list_file: Path) -> Path:
    path = Path(raw_path.strip().strip('"'))
    if path.is_absolute():
        return path
    return list_file.parent / path


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def relative_path_key(path: Path, root: Path) -> str:
    try:
        relative_path = FILE_SYSTEM.resolved_relative_path(path, root)
    except ValueError:
        relative_path = path
    return os.path.normcase(str(relative_path))


def unique_paths(paths: list[Path]) -> list[Path]:
    seen = set()
    unique = []
    for path in paths:
        key = path_key(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def missing_paths_from_file(list_file: Path) -> list[Path]:
    paths = []
    for line in FILE_SYSTEM.read_text(list_file).splitlines():
        stripped = line.strip()
        if stripped:
            paths.append(resolve_listed_path(stripped, list_file))
    return unique_paths(paths)


def input_paths_from_csv(csv_file: Path, path_column: str) -> list[Path]:
    paths = []
    with FILE_SYSTEM.open_csv(csv_file) as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit(f"CSV-Datei hat keine Kopfzeile: {csv_file}")

        matching_columns = [
            fieldname
            for fieldname in reader.fieldnames
            if fieldname and fieldname.casefold() == path_column.casefold()
        ]
        if not matching_columns:
            available = ", ".join(reader.fieldnames)
            raise SystemExit(
                f"CSV-Spalte nicht gefunden: {path_column}. Verfuegbar: {available}"
            )

        actual_column = matching_columns[0]
        for row in reader:
            raw_path = (row.get(actual_column) or "").strip()
            if raw_path:
                paths.append(resolve_listed_path(raw_path, csv_file))
    return unique_paths(paths)


def update_used_original_files(
    csv_file: Path,
    used_original_files: Path,
    path_column: str,
) -> tuple[list[Path], int, int]:
    existing_paths = (
        missing_paths_from_file(used_original_files)
        if FILE_SYSTEM.is_file(used_original_files)
        else []
    )
    csv_paths = (
        input_paths_from_csv(csv_file, path_column)
        if FILE_SYSTEM.is_file(csv_file)
        else []
    )
    combined_paths = unique_paths(existing_paths + csv_paths)
    added = len(combined_paths) - len(existing_paths)

    FILE_SYSTEM.write_text(
        used_original_files,
        "\n".join(str(path) for path in combined_paths)
        + ("\n" if combined_paths else ""),
    )
    return combined_paths, len(csv_paths), added


def common_parent(paths: list[Path]) -> Path | None:
    parent_paths = [str(path.parent) for path in paths if path.parent]
    if not parent_paths:
        return None

    try:
        return Path(os.path.commonpath(parent_paths))
    except ValueError:
        return None


def remove_used_paths_missing_from_source(
    used_file_paths: list[Path],
    search_dir: Path,
    recursive: bool,
    input_root: Path | None,
) -> tuple[list[Path], list[Path]]:
    effective_input_root = input_root or common_parent(used_file_paths)
    source_files = FILE_SYSTEM.files_in(search_dir, recursive)
    source_path_keys = {path_key(path) for path in source_files}
    source_relative_keys = {
        relative_path_key(path, search_dir) for path in source_files
    }

    kept_paths = []
    removed_paths = []
    for path in used_file_paths:
        exists_in_source = path_key(path) in source_path_keys
        if effective_input_root:
            exists_in_source = exists_in_source or (
                relative_path_key(path, effective_input_root)
                in source_relative_keys
            )

        if exists_in_source:
            kept_paths.append(path)
        else:
            removed_paths.append(path)

    return kept_paths, removed_paths


def find_missing_files(
    used_file_paths: list[Path],
    search_dir: Path,
    recursive: bool,
    ascending: bool,
    input_root: Path | None,
) -> list[Path]:
    listed_paths = {path_key(path) for path in used_file_paths}

    effective_input_root = input_root or common_parent(used_file_paths)
    listed_relative_paths = (
        {relative_path_key(path, effective_input_root) for path in used_file_paths}
        if effective_input_root
        else set()
    )

    found_files = FILE_SYSTEM.files_in(search_dir, recursive)

    missing_files = [
        path
        for path in found_files
        if path_key(path) not in listed_paths
        and relative_path_key(path, search_dir) not in listed_relative_paths
    ]
    return sorted(
        missing_files,
        key=lambda path: (FILE_SYSTEM.file_size(path), str(path).casefold()),
        reverse=not ascending,
    )


def write_lines(lines: list[str], output_file: Path) -> None:
    text = "\n".join(lines) + ("\n" if lines else "")
    FILE_SYSTEM.write_text(output_file, text)


def supports_color(stream: object) -> bool:
    is_terminal = getattr(stream, "isatty", lambda: False)()
    if not is_terminal or "NO_COLOR" in os.environ:
        return False
    if os.name != "nt":
        return True

    try:
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = ctypes.c_ulong()
        kernel32 = ctypes.windll.kernel32
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError, ValueError):
        return False


def colored(message: str, color: str, stream: object) -> str:
    if not supports_color(stream):
        return message
    return f"{color}{message}{ANSI_RESET}"


def show_progress(message: str, color: str | None = None) -> None:
    output = colored(message, color, sys.stderr) if color else message
    print(output, file=sys.stderr, flush=True)


def path_relative_to_source(path: Path, source_dir: Path) -> Path:
    try:
        return FILE_SYSTEM.resolved_relative_path(path, source_dir)
    except ValueError as error:
        raise SystemExit(
            f"Pfad aus {UNUSED_ORIGINAL_FILES_NAME} liegt nicht unter "
            f"--missing-in: {path}"
        ) from error


def remove_stale_zero_byte_files(
    missing_relative_paths: set[Path],
    source_dir: Path,
    target_dir: Path,
    recursive: bool,
) -> int:
    removed = 0
    for target_path in FILE_SYSTEM.files_in(target_dir, recursive):
        if not FILE_SYSTEM.is_empty_file(target_path):
            continue

        relative_path = FILE_SYSTEM.relative_path(target_path, target_dir)
        if relative_path not in missing_relative_paths:
            source_path = source_dir / relative_path
            if FILE_SYSTEM.is_empty_file(source_path):
                continue
            FILE_SYSTEM.remove_file(target_path)
            removed += 1
    return removed


def create_zero_byte_files(
    missing_relative_paths: set[Path],
    target_dir: Path,
) -> int:
    emptied = 0
    for relative_path in missing_relative_paths:
        target_path = target_dir / relative_path
        if FILE_SYSTEM.is_empty_file(target_path):
            continue
        FILE_SYSTEM.create_empty_file(target_path)
        emptied += 1
    return emptied


def copy_missing_original_files(
    missing_relative_paths: set[Path],
    source_dir: Path,
    target_dir: Path,
    recursive: bool,
) -> tuple[int, int]:
    copied = 0
    already_present = 0
    for source_path in FILE_SYSTEM.files_in(source_dir, recursive):
        relative_path = FILE_SYSTEM.relative_path(source_path, source_dir)
        if relative_path in missing_relative_paths:
            continue

        target_path = target_dir / relative_path
        if FILE_SYSTEM.exists(target_path):
            already_present += 1
            continue

        FILE_SYSTEM.copy_file(source_path, target_path)
        copied += 1
    return copied, already_present


@dataclass(frozen=True)
class MergeStats:
    removed: int = 0
    emptied: int = 0
    copied: int = 0
    already_present: int = 0


def merge_result(
    missing_file_paths: list[Path],
    source_dir: Path,
    target_dir: Path,
    recursive: bool,
) -> MergeStats:
    missing_relative_paths = {
        path_relative_to_source(path, source_dir)
        for path in unique_paths(missing_file_paths)
    }

    show_progress("[5/7] Veraltete 0-Byte-Dateien entfernen ...")
    removed = remove_stale_zero_byte_files(
        missing_relative_paths,
        source_dir,
        target_dir,
        recursive,
    )
    show_progress(f"      Entfernt: {removed}", ANSI_RED if removed else None)

    show_progress("[6/7] Aktuelle 0-Byte-Dateien erzeugen ...")
    emptied = create_zero_byte_files(missing_relative_paths, target_dir)
    show_progress(
        f"      Erzeugt/auf 0 Byte gesetzt: {emptied}",
        ANSI_GREEN if emptied else None,
    )

    show_progress("[7/7] Fehlende Originaldateien kopieren ...")
    copied, already_present = copy_missing_original_files(
        missing_relative_paths,
        source_dir,
        target_dir,
        recursive,
    )
    show_progress(
        f"      Kopiert: {copied}; bereits im Ziel vorhanden: {already_present}",
        ANSI_GREEN if copied else None,
    )

    return MergeStats(removed, emptied, copied, already_present)


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sammelt verwendete Dateipfade dauerhaft aus CSV-Dateien, findet "
            "nicht verwendete Dateien und kann daraus einen zusammengefuehrten "
            "Zielordner erstellen."
        )
    )
    parser.add_argument(
        "inputdatei",
        type=Path,
        help=(
            "Pfad zur CSV-Datei mit einer Path-Spalte. Die CSV darf fehlen, "
            "wenn daneben bereits used_original_files.txt vorhanden ist."
        ),
    )
    parser.add_argument(
        "-a",
        "--ascending",
        action="store_true",
        help="Kleinste Dateien zuerst sortieren. Standard ist groesste zuerst.",
    )
    parser.add_argument(
        "--missing-in",
        type=Path,
        metavar="ORDNER",
        help=(
            "Gibt Dateien aus diesem Ordner aus, die nicht in der zentralen "
            "Pfadliste stehen."
        ),
    )
    parser.add_argument(
        "--path-column",
        default="Path",
        help="Name der CSV-Spalte mit den Dateipfaden. Standard: Path.",
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        metavar="ORDNER",
        help=(
            "Basisordner der gespeicherten Pfade fuer relative Vergleiche. Ohne "
            "diese Option wird der gemeinsame Pfad-Ordner automatisch erkannt."
        ),
    )
    parser.add_argument(
        "--merge-result-to",
        type=Path,
        metavar="ORDNER",
        help=(
            "Fuehrt den Inhalt von --missing-in im Ziel zusammen. Dateien aus "
            "unused_original_files.txt werden dort als 0-Byte-Dateien angelegt; "
            "veraltete 0-Byte-Dateien werden durch ihre Originale ersetzt."
        ),
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Mit --missing-in auch Unterordner durchsuchen.",
    )
    return parser


@dataclass(frozen=True)
class RunPaths:
    input_file: Path
    used_file: Path
    unused_file: Path
    search_dir: Path
    target_dir: Path | None


def resolve_run_paths(args: argparse.Namespace) -> RunPaths:
    input_file = FILE_SYSTEM.resolve(args.inputdatei)
    if input_file.suffix.casefold() != ".csv":
        raise SystemExit("Die Inputdatei muss eine CSV-Datei sein.")

    used_file = input_file.parent / USED_ORIGINAL_FILES_NAME
    unused_file = input_file.parent / UNUSED_ORIGINAL_FILES_NAME
    if not FILE_SYSTEM.is_file(input_file) and not FILE_SYSTEM.is_file(used_file):
        raise SystemExit(
            f"Weder Inputdatei noch zentrale Pfadliste gefunden: {input_file}; "
            f"{used_file}"
        )

    if not args.missing_in:
        raise SystemExit("Bitte --missing-in angeben.")

    search_dir = FILE_SYSTEM.resolve(args.missing_in)
    if not FILE_SYSTEM.is_directory(search_dir):
        raise SystemExit(f"Suchordner nicht gefunden: {search_dir}")

    target_dir = (
        FILE_SYSTEM.resolve(args.merge_result_to) if args.merge_result_to else None
    )
    if target_dir and FILE_SYSTEM.is_same_or_within(target_dir, search_dir):
        raise SystemExit(
            "--merge-result-to darf nicht --missing-in selbst oder ein "
            "Unterordner davon sein."
        )

    return RunPaths(input_file, used_file, unused_file, search_dir, target_dir)


@dataclass(frozen=True)
class UsedUpdate:
    paths: list[Path]
    added_count: int
    removed_paths: list[Path]


def refresh_used_files(
    paths: RunPaths,
    args: argparse.Namespace,
    total_steps: int,
) -> UsedUpdate:
    show_progress(
        f"[1/{total_steps}] Zentrale Pfadliste aktualisieren: "
        f"{paths.used_file}"
    )
    used_file_paths, csv_path_count, added_count = update_used_original_files(
        paths.input_file,
        paths.used_file,
        args.path_column,
    )
    show_progress(
        f"      Aus CSV gelesen: {csv_path_count}; neu ergaenzt: {added_count}; "
        f"gesamt gespeichert: {len(used_file_paths)}",
        ANSI_GREEN if added_count else None,
    )

    show_progress(
        f"[2/{total_steps}] Nicht mehr vorhandene Used-Eintraege entfernen ..."
    )
    used_file_paths, removed_used_paths = remove_used_paths_missing_from_source(
        used_file_paths,
        paths.search_dir,
        args.recursive,
        args.input_root,
    )
    for removed_path in removed_used_paths:
        show_progress(f"      Entfernt: {removed_path}", ANSI_RED)
    write_lines([str(path) for path in used_file_paths], paths.used_file)
    show_progress(
        f"      Entfernt: {len(removed_used_paths)}; "
        f"verbleibend: {len(used_file_paths)}",
        ANSI_RED if removed_used_paths else None,
    )
    return UsedUpdate(used_file_paths, added_count, removed_used_paths)


def refresh_unused_files(
    used_file_paths: list[Path],
    paths: RunPaths,
    args: argparse.Namespace,
    total_steps: int,
) -> None:
    show_progress(f"[3/{total_steps}] Nicht verwendete Dateien ermitteln ...")
    missing_files = find_missing_files(
        used_file_paths,
        paths.search_dir,
        args.recursive,
        args.ascending,
        args.input_root,
    )
    show_progress(f"      Gefunden: {len(missing_files)}")

    show_progress(
        f"[4/{total_steps}] Liste schreiben: {paths.unused_file}"
    )
    write_lines([str(path) for path in missing_files], paths.unused_file)


def run_optional_merge(paths: RunPaths, recursive: bool) -> MergeStats:
    if not paths.target_dir:
        return MergeStats()
    missing_files = missing_paths_from_file(paths.unused_file)
    return merge_result(
        missing_files,
        paths.search_dir,
        paths.target_dir,
        recursive,
    )


def print_summary(used_update: UsedUpdate, merge_stats: MergeStats) -> None:
    changes = []
    if used_update.added_count:
        changes.append(
            colored(
                f"Used-Eintraege hinzugefuegt: {used_update.added_count}",
                ANSI_GREEN,
                sys.stdout,
            )
        )
    if used_update.removed_paths:
        changes.append(
            colored(
                "Veraltete Used-Eintraege entfernt: "
                f"{len(used_update.removed_paths)}",
                ANSI_RED,
                sys.stdout,
            )
        )
    if merge_stats.removed:
        changes.append(
            colored(
                f"Veraltete 0-Byte-Dateien entfernt: {merge_stats.removed}",
                ANSI_RED,
                sys.stdout,
            )
        )
    if merge_stats.emptied:
        changes.append(
            colored(
                "0-Byte-Dateien erzeugt/aktualisiert: "
                f"{merge_stats.emptied}",
                ANSI_GREEN,
                sys.stdout,
            )
        )
    if merge_stats.copied:
        changes.append(
            colored(
                f"Originale kopiert: {merge_stats.copied}",
                ANSI_GREEN,
                sys.stdout,
            )
        )

    print("Fertig. " + ("; ".join(changes) if changes else "Keine Aenderungen."))


def main() -> None:
    args = create_argument_parser().parse_args()
    paths = resolve_run_paths(args)
    total_steps = 7 if paths.target_dir else 4

    used_update = refresh_used_files(paths, args, total_steps)
    refresh_unused_files(used_update.paths, paths, args, total_steps)
    merge_stats = run_optional_merge(paths, args.recursive)
    print_summary(used_update, merge_stats)


if __name__ == "__main__":
    main()
