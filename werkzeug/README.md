# Werkzeug

Hiermit wird das Chill-Zone-Spielpaket für die Releases gebaut.

- `build_release.py` liest den lokalen Spielclient und baut daraus `ChillZone-Paket-<version>.zip`, `release.json` und `mod-lizenzen.csv`.
  Aufruf: `python -I build_release.py 0.5.0`
- `mod-lizenzen.csv` ist die Übersicht zu Paket 0.5.0: jede Datei mit Herkunft, Lizenz, SHA256 und Modrinth-Link.

## Regeln

- Fremde Mods und Pakete verteilen wir nicht selbst. Sie bekommen in `release.json` eine `Url` auf `https://cdn.modrinth.com`. Der Launcher lädt sie dort und prüft den SHA256.
- Ins ZIP kommen nur eigene Projektdateien oder Dateien mit freier Lizenz.
- In diesem Repo liegen keine Mods, nur Code und Listen.

## Neues Release

1. Script ausführen und `BUILD-REPORT.json` prüfen.
2. GitHub-Release `v<version>` anlegen und `ChillZone-Paket-<version>.zip` und `release.json` als Assets hochladen.
3. Die Launcher lesen `https://github.com/linox55555-prog/chillzone-updates/releases/latest/download/release.json`.
