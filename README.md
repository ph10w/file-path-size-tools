# Merge Unused Files

Kleines Python-Werkzeug zum Arbeiten mit Procmon-/Log-CSV-Dateien.

## Funktionen

- CSV-Datei mit Spalte `Path` als Input verwenden
- Verwendete Pfade dauerhaft in `used_original_files.txt` sammeln
- Nicht verwendete Pfade automatisch in `unused_original_files.txt` schreiben
- Ergebnis standardmaessig nach Dateigroesse absteigend sortieren
- Fehlende Dateien als 0-Byte-Dateien mit vorhandenen Originaldateien zusammenfuehren
- Fortschritt und Anzahl der bearbeiteten Dateien je Arbeitsschritt anzeigen

## Zentrale Pfadliste

Beim ersten Lauf werden im Ordner der Input-CSV automatisch `used_original_files.txt` und `unused_original_files.txt` erzeugt. Bei `outputs\Logfile.CSV` liegen die Dateien somit ebenfalls unter `outputs`.

Jede neue CSV ergaenzt nur Pfade, die noch nicht in dieser TXT-Datei gespeichert sind. Vorhandene Pfade bleiben erhalten, auch wenn sie in einer spaeteren CSV nicht mehr vorkommen. Nach einem erfolgreichen Lauf kann `Logfile.CSV` geloescht werden. Derselbe Programmaufruf verwendet dann weiterhin `used_original_files.txt`, solange keine neue CSV vorhanden ist.

## Parameter

```text
inputdatei
```

CSV-Datei mit einer `Path`-Spalte. Neben der CSV wird automatisch `used_original_files.txt` angelegt. Ist die CSV nicht mehr vorhanden, wird die bestehende TXT-Datei weiterhin als zentrale Pfadquelle verwendet.

```text
--missing-in ORDNER
```

Durchsucht `ORDNER` und gibt alle Dateien aus, die nicht in `used_original_files.txt` stehen. Die Ausgabe ist standardmaessig nach Dateigroesse absteigend sortiert, also groesste Dateien zuerst.

```text
-a, --ascending
```

Sortiert die Ausgabe von `--missing-in` aufsteigend nach Dateigroesse, also kleinste Dateien zuerst.

```text
-r, --recursive
```

Durchsucht mit `--missing-in` auch Unterordner.

```text
--path-column NAME
```

Name der CSV-Spalte mit den Dateipfaden. Standard ist `Path`.

```text
--input-root ORDNER
```

Basisordner der gesammelten Pfade fuer relative Vergleiche. Das ist hilfreich, wenn die CSV z.B. `R:\Win\...` enthaelt, die echten Dateien aber unter `D:\GameTools\Hearthstone\Data\Win\...` liegen. Ohne diese Option wird der gemeinsame Ordner der gespeicherten Pfade automatisch erkannt.

```text
--merge-result-to ORDNER
```

Erstellt in `ORDNER` ein zusammengefuehrtes Ergebnis. Zuerst werden vorhandene 0-Byte-Dateien entfernt, die nicht mehr in der aktuellen Datei `unused_original_files.txt` stehen. Danach werden alle aktuell nicht verwendeten Dateien mit ihrer relativen Ordnerstruktur als 0-Byte-Dateien angelegt oder auf 0 Byte gekuerzt. Abschliessend werden alle uebrigen Dateien aus `--missing-in`, die im Ziel nicht existieren, unveraendert kopiert. Dadurch wird eine wieder verwendete Datei durch das Original ersetzt. Bereits vorhandene Originaldateien im Ziel bleiben unveraendert.

## Beispiele

Fehlende Dateien aus einem Ordner gegen eine CSV pruefen:

```powershell
python merge_unused_files.py outputs\Logfile.CSV --missing-in R:\Win
```

Wenn die CSV-Pfade einen anderen Root haben als der Suchordner:

```powershell
python merge_unused_files.py outputs\Logfile.CSV --missing-in D:\GameTools\Hearthstone\Data\Win --input-root R:\Win
```

Kleinste fehlende Dateien zuerst ausgeben:

```powershell
python merge_unused_files.py outputs\Logfile.CSV --missing-in R:\Win --ascending
```

Zusammengefuehrten Zielordner erstellen:

```powershell
python merge_unused_files.py outputs\Logfile.CSV --missing-in D:\GameTools\Hearthstone\Data\Win --input-root R:\Win --merge-result-to D:\GameTools\HS\merged
```

Der gleiche Aufruf funktioniert nach dem Loeschen von `outputs\Logfile.CSV` weiter, sofern `outputs\used_original_files.txt` bereits erzeugt wurde. Eine spaeter neu angelegte `Logfile.CSV` ergaenzt beim naechsten Lauf wieder nur neue Pfade.

Mit `--recursive` werden dabei auch Unterordner durchsucht und in das Ziel uebernommen.

Hilfe anzeigen:

```powershell
python merge_unused_files.py --help
```
