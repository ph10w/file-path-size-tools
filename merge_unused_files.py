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
from pathlib import Path

USED_ORIGINAL_FILES_NAME = "used_original_files.txt"
UNUSED_ORIGINAL_FILES_NAME = "unused_original_files.txt"


def resolve_listed_path(raw_path: str, list_file: Path) -> Path:
    path = Path(raw_path.strip().strip('"'))
    if path.is_absolute():
        return path
    return list_file.parent / path


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def relative_path_key(path: Path, root: Path) -> str:
    try:
        relative_path = path.resolve(strict=False).relative_to(root.resolve(strict=False))
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
    for line in list_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            paths.append(resolve_listed_path(stripped, list_file))
    return unique_paths(paths)


def input_paths_from_csv(csv_file: Path, path_column: str) -> list[Path]:
    paths = []
    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
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
        if used_original_files.is_file()
        else []
    )
    csv_paths = (
        input_paths_from_csv(csv_file, path_column) if csv_file.is_file() else []
    )
    combined_paths = unique_paths(existing_paths + csv_paths)
    added = len(combined_paths) - len(existing_paths)

    used_original_files.parent.mkdir(parents=True, exist_ok=True)
    used_original_files.write_text(
        "\n".join(str(path) for path in combined_paths)
        + ("\n" if combined_paths else ""),
        encoding="utf-8",
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

    pattern = "**/*" if recursive else "*"
    found_files = [path for path in search_dir.glob(pattern) if path.is_file()]

    missing_files = [
        path
        for path in found_files
        if path_key(path) not in listed_paths
        and relative_path_key(path, search_dir) not in listed_relative_paths
    ]
    return sorted(
        missing_files,
        key=lambda path: (path.stat().st_size, str(path).casefold()),
        reverse=not ascending,
    )


def write_lines(lines: list[str], output_file: Path) -> None:
    text = "\n".join(lines) + ("\n" if lines else "")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(text, encoding="utf-8")


def show_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def path_relative_to_source(path: Path, source_dir: Path) -> Path:
    try:
        return path.resolve(strict=False).relative_to(source_dir.resolve(strict=False))
    except ValueError as error:
        raise SystemExit(
            f"Pfad aus {UNUSED_ORIGINAL_FILES_NAME} liegt nicht unter "
            f"--missing-in: {path}"
        ) from error


def merge_result(
    missing_file_paths: list[Path],
    source_dir: Path,
    target_dir: Path,
    recursive: bool,
) -> tuple[int, int, int, int]:
    missing_relative_paths = {
        path_relative_to_source(path, source_dir)
        for path in unique_paths(missing_file_paths)
    }

    pattern = "**/*" if recursive else "*"
    show_progress("[4/6] Veraltete 0-Byte-Dateien entfernen ...")
    removed = 0
    for target_path in target_dir.glob(pattern):
        if not target_path.is_file() or target_path.stat().st_size != 0:
            continue

        relative_path = target_path.relative_to(target_dir)
        if relative_path not in missing_relative_paths:
            target_path.unlink()
            removed += 1
    show_progress(f"      Entfernt: {removed}")

    show_progress("[5/6] Aktuelle 0-Byte-Dateien erzeugen ...")
    emptied = 0
    for relative_path in missing_relative_paths:
        target_path = target_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"")
        emptied += 1
    show_progress(f"      Auf 0 Byte gesetzt: {emptied}")

    show_progress("[6/6] Fehlende Originaldateien kopieren ...")
    copied = 0
    already_present = 0
    for source_path in source_dir.glob(pattern):
        if not source_path.is_file():
            continue

        relative_path = source_path.relative_to(source_dir)
        if relative_path in missing_relative_paths:
            continue

        target_path = target_dir / relative_path
        if target_path.exists():
            already_present += 1
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied += 1
    show_progress(
        f"      Kopiert: {copied}; bereits im Ziel vorhanden: {already_present}"
    )

    return removed, emptied, copied, already_present


def main() -> None:
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
    args = parser.parse_args()

    input_file = args.inputdatei.resolve()
    if input_file.suffix.casefold() != ".csv":
        raise SystemExit("Die Inputdatei muss eine CSV-Datei sein.")

    used_original_files = input_file.parent / USED_ORIGINAL_FILES_NAME
    unused_original_files = input_file.parent / UNUSED_ORIGINAL_FILES_NAME
    if not input_file.is_file() and not used_original_files.is_file():
        raise SystemExit(
            f"Weder Inputdatei noch zentrale Pfadliste gefunden: {input_file}; "
            f"{used_original_files}"
        )

    if not args.missing_in:
        raise SystemExit("Bitte --missing-in angeben.")

    search_dir = args.missing_in.resolve()
    if not search_dir.is_dir():
        raise SystemExit(f"Suchordner nicht gefunden: {search_dir}")

    total_steps = 6 if args.merge_result_to else 3
    show_progress(
        f"[1/{total_steps}] Zentrale Pfadliste aktualisieren: "
        f"{used_original_files}"
    )
    used_file_paths, csv_path_count, added_count = update_used_original_files(
        input_file,
        used_original_files,
        args.path_column,
    )
    show_progress(
        f"      Aus CSV gelesen: {csv_path_count}; neu ergaenzt: {added_count}; "
        f"gesamt gespeichert: {len(used_file_paths)}"
    )

    show_progress(f"[2/{total_steps}] Nicht verwendete Dateien ermitteln ...")
    missing_files = find_missing_files(
        used_file_paths,
        search_dir,
        args.recursive,
        args.ascending,
        args.input_root,
    )
    show_progress(f"      Gefunden: {len(missing_files)}")

    show_progress(
        f"[3/{total_steps}] Liste schreiben: {unused_original_files}"
    )
    write_lines([str(path) for path in missing_files], unused_original_files)

    if args.merge_result_to:
        target_dir = args.merge_result_to.resolve()
        try:
            target_dir.relative_to(search_dir)
        except ValueError:
            pass
        else:
            raise SystemExit(
                "--merge-result-to darf nicht --missing-in selbst oder ein "
                "Unterordner davon sein."
            )

        listed_missing_files = missing_paths_from_file(unused_original_files)
        removed, emptied, copied, already_present = merge_result(
            listed_missing_files,
            search_dir,
            target_dir,
            args.recursive,
        )
        print(
            f"Fertig. Veraltete 0-Byte-Dateien entfernt: {removed}; "
            f"auf 0 Byte gesetzt: {emptied}; Originale kopiert: {copied}; "
            f"bereits vorhanden: {already_present}"
        )


if __name__ == "__main__":
    main()
