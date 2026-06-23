#!/usr/bin/env python3
"""
Sort a text file or CSV file containing file paths by the referenced file sizes.

Usage:
    python sort_file_paths_by_size.py pfade.txt
    python sort_file_paths_by_size.py Logfile.CSV --missing-in C:\\Dateien
    python sort_file_paths_by_size.py fehlende.txt --create-empty-in C:\\Platzhalter
    python sort_file_paths_by_size.py fehlende.txt --create-empty-in C:\\Platzhalter --relative-to C:\\Dateien
    python sort_file_paths_by_size.py pfade.txt --descending
    python sort_file_paths_by_size.py pfade.txt --output sortiert.txt
    python sort_file_paths_by_size.py pfade.txt --missing-in C:\\Dateien
    python sort_file_paths_by_size.py pfade.txt --missing-in C:\\Dateien --recursive --output fehlende.txt

By default, missing files are kept and sorted after existing files.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path


def resolve_listed_path(raw_path: str, list_file: Path) -> Path:
    path = Path(raw_path.strip().strip('"'))
    if path.is_absolute():
        return path
    return list_file.parent / path


def sort_key(line: str, list_file: Path) -> tuple[int, int, str]:
    stripped = line.strip()
    if not stripped:
        return (1, 0, line.casefold())

    path = resolve_listed_path(stripped, list_file)
    try:
        return (0, path.stat().st_size, line.casefold())
    except OSError:
        return (1, 0, line.casefold())


def sort_path_file(
    list_file: Path,
    output_file: Path | None,
    descending: bool,
    skip_missing: bool,
) -> None:
    lines = list_file.read_text(encoding="utf-8").splitlines()

    if skip_missing:
        lines = [
            line
            for line in lines
            if line.strip() and resolve_listed_path(line, list_file).is_file()
        ]

    sorted_lines = sorted(lines, key=lambda line: sort_key(line, list_file))
    if descending:
        existing = [line for line in sorted_lines if sort_key(line, list_file)[0] == 0]
        missing = [line for line in sorted_lines if sort_key(line, list_file)[0] == 1]
        sorted_lines = list(reversed(existing)) + missing

    target = output_file or list_file
    target.write_text("\n".join(sorted_lines) + ("\n" if sorted_lines else ""), encoding="utf-8")


def normalize_path(path: Path) -> Path:
    return path.resolve(strict=False)


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def is_csv_file(path: Path) -> bool:
    return path.suffix.casefold() == ".csv"


def unique_paths(paths: list[Path]) -> list[Path]:
    seen = set()
    unique = []
    for path in paths:
        key = path_key(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def input_paths_from_text(list_file: Path) -> list[Path]:
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


def input_paths(input_file: Path, path_column: str) -> list[Path]:
    if is_csv_file(input_file):
        return input_paths_from_csv(input_file, path_column)
    return input_paths_from_text(input_file)


def listed_file_paths_from_text(list_file: Path) -> set[str]:
    return {path_key(path) for path in input_paths_from_text(list_file)}


def listed_file_paths_from_csv(csv_file: Path, path_column: str) -> set[str]:
    return {path_key(path) for path in input_paths_from_csv(csv_file, path_column)}


def listed_file_paths(input_file: Path, path_column: str) -> set[str]:
    if is_csv_file(input_file):
        return listed_file_paths_from_csv(input_file, path_column)
    return listed_file_paths_from_text(input_file)


def find_missing_files(
    input_file: Path,
    search_dir: Path,
    recursive: bool,
    descending: bool,
    path_column: str,
) -> list[Path]:
    listed_paths = listed_file_paths(input_file, path_column)
    pattern = "**/*" if recursive else "*"
    found_files = [path for path in search_dir.glob(pattern) if path.is_file()]

    missing_files = [path for path in found_files if path_key(path) not in listed_paths]
    return sorted(
        missing_files,
        key=lambda path: (path.stat().st_size, str(path).casefold()),
        reverse=descending,
    )


def write_or_print_lines(lines: list[str], output_file: Path | None) -> None:
    text = "\n".join(lines) + ("\n" if lines else "")
    if output_file:
        output_file.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def safe_path_part(part: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    safe = "".join("_" if char in invalid_chars else char for char in part)
    safe = safe.rstrip(" .")
    return safe or "_"


def placeholder_relative_path(source_path: Path, relative_to: Path | None) -> Path:
    if relative_to:
        try:
            return source_path.resolve(strict=False).relative_to(relative_to.resolve(strict=False))
        except ValueError:
            pass

    if source_path.is_absolute():
        drive = safe_path_part(source_path.drive.rstrip(":")) if source_path.drive else None
        parts = list(source_path.parts[1:])
        if drive:
            parts.insert(0, drive)
        return Path(*[safe_path_part(part) for part in parts])

    return Path(*[safe_path_part(part) for part in source_path.parts])


def create_empty_files(
    source_paths: list[Path],
    target_dir: Path,
    relative_to: Path | None,
    overwrite: bool,
) -> tuple[int, int]:
    created = 0
    existing = 0
    for source_path in unique_paths(source_paths):
        target_path = target_dir / placeholder_relative_path(source_path, relative_to)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            existing += 1
            if overwrite:
                target_path.write_bytes(b"")
            continue

        target_path.write_bytes(b"")
        created += 1
    return created, existing


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sortiert eine Textdatei mit Dateipfaden nach Dateigroesse oder gibt "
            "Dateien aus einem Ordner aus, die nicht in einer Text-/CSV-Datei stehen."
        )
    )
    parser.add_argument(
        "inputdatei",
        type=Path,
        help="Textdatei mit einem Pfad pro Zeile oder CSV-Datei mit einer Path-Spalte.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "Ausgabedatei. Beim Sortieren der Pfade-Datei wird ohne diese Option "
            "die Textdatei direkt ueberschrieben. Mit --missing-in wird ohne diese "
            "Option auf die Konsole geschrieben."
        ),
    )
    parser.add_argument(
        "-d",
        "--descending",
        action="store_true",
        help="Groesste Dateien zuerst sortieren.",
    )
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="Nicht vorhandene Dateien aus der Ausgabe entfernen.",
    )
    parser.add_argument(
        "--missing-in",
        type=Path,
        metavar="ORDNER",
        help="Gibt Dateien aus diesem Ordner aus, die nicht in der Inputdatei stehen.",
    )
    parser.add_argument(
        "--path-column",
        default="Path",
        help="Name der CSV-Spalte mit den Dateipfaden. Standard: Path.",
    )
    parser.add_argument(
        "--create-empty-in",
        type=Path,
        metavar="ORDNER",
        help="Erzeugt fuer die ermittelten Pfade leere 0-Byte-Dateien in diesem Ordner.",
    )
    parser.add_argument(
        "--relative-to",
        type=Path,
        metavar="ORDNER",
        help="Entfernt diesen Ursprungspfad beim Erzeugen der Platzhalterstruktur.",
    )
    parser.add_argument(
        "--overwrite-placeholders",
        action="store_true",
        help="Bereits vorhandene Platzhalterdateien auf 0 Byte kuerzen.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Mit --missing-in auch Unterordner durchsuchen.",
    )
    args = parser.parse_args()

    input_file = args.inputdatei.resolve()
    if not input_file.is_file():
        raise SystemExit(f"Inputdatei nicht gefunden: {input_file}")

    output_file = args.output.resolve() if args.output else None
    paths_for_placeholders: list[Path] | None = None
    if args.missing_in:
        search_dir = args.missing_in.resolve()
        if not search_dir.is_dir():
            raise SystemExit(f"Suchordner nicht gefunden: {search_dir}")

        missing_files = find_missing_files(
            input_file,
            search_dir,
            args.recursive,
            args.descending,
            args.path_column,
        )
        paths_for_placeholders = missing_files
        write_or_print_lines([str(path) for path in missing_files], output_file)
    else:
        if args.create_empty_in:
            paths_for_placeholders = input_paths(input_file, args.path_column)
        elif is_csv_file(input_file):
            raise SystemExit(
                "CSV-Input wird fuer --missing-in unterstuetzt. "
                "Zum Sortieren der CSV selbst bitte eine Textdatei mit Pfaden verwenden."
            )
        else:
            sort_path_file(input_file, output_file, args.descending, args.skip_missing)

    if args.create_empty_in and paths_for_placeholders is not None:
        target_dir = args.create_empty_in.resolve()
        relative_to = args.relative_to.resolve() if args.relative_to else None
        created, existing = create_empty_files(
            paths_for_placeholders,
            target_dir,
            relative_to,
            args.overwrite_placeholders,
        )
        print(f"Platzhalter erstellt: {created}; bereits vorhanden: {existing}")


if __name__ == "__main__":
    main()
