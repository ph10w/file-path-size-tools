# File Path Size Tools

Kleines Python-Werkzeug zum Arbeiten mit Dateipfadlisten und Procmon-/Log-CSV-Dateien.

## Funktionen

- Textdatei mit Pfaden nach Dateigroesse sortieren
- CSV-Datei mit Spalte `Path` als Input verwenden
- Dateien aus einem Ordner ausgeben, die nicht in der Pfadliste/CSV enthalten sind
- Ergebnis nach Dateigroesse auf- oder absteigend sortieren
- Leere 0-Byte-Platzhalterdateien in einem eigenen Ordner erzeugen

## Beispiele

Fehlende Dateien aus einem Ordner gegen eine CSV pruefen:

```powershell
python outputs\sort_file_paths_by_size.py outputs\Logfile.CSV --missing-in R:\Win --output outputs\fehlende_desc.txt --descending
```

0-Byte-Platzhalter fuer eine Ergebnisliste erzeugen:

```powershell
python outputs\sort_file_paths_by_size.py outputs\fehlende_desc.txt --create-empty-in C:\Temp\Platzhalter --relative-to R:\Win
```

Hilfe anzeigen:

```powershell
python outputs\sort_file_paths_by_size.py --help
```
