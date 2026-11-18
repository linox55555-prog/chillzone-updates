# Chill Zone Updates

Update-Feed für die Chill-Zone-Launcher (Minecraft 1.21.8, Fabric). Jedes Update ist ein GitHub-Release `v<version>` mit zwei Assets:

- `ChillZone-Paket-<version>.zip` mit eigenen Projektdateien und Dateien mit freier Lizenz
- `release.json`, das Manifest (Schema 1)

Die Launcher lesen immer
`https://github.com/linox55555-prog/chillzone-updates/releases/latest/download/release.json`.

## So funktioniert es

- `release.json` listet unter `Files` jede Datei mit `Path`, `Sha256` und `Size`.
  **Fremde Mods und Packs** liegen nicht im ZIP. Sie haben ein Feld `Url` auf `https://cdn.modrinth.com/...`.
  Der Launcher lädt sie dort und prüft den SHA256. Andere Hosts lehnt er ab.
- `Removals` listet alte Dateien (`Path` + `OldSha256`). Der Launcher löscht sie nur, wenn der SHA256 passt.
- Verwaltet werden **nur** `mods/`, `resourcepacks/` und `shaderpacks/`. Persönliche Daten (Welten, Karten, `options.txt`) und `config/` werden nie angefasst.

## Neues Update Schritt für Schritt

1. **Testen:** Änderungen zuerst im lokalen Spielclient (`mods/`, `resourcepacks/`, `shaderpacks/`) im Spiel testen.
2. **Bauen:** `python -I build_release.py <neue Version>` (siehe [`werkzeug/`](werkzeug/)).
   Die Version muss höher sein als die letzte. Ohne Argument baut das Skript 0.5.0, also immer eine Version angeben.
   Die Ausgabe landet im Ordner des Skripts und überschreibt dort den letzten Bau: `ChillZone-Paket-<version>.zip`, `release.json`, `mod-lizenzen.csv`, `BUILD-REPORT.json`.
   In `BUILD-REPORT.json` müssen `serverRequiredButSkipped` und `removalProblems` leer sein.
3. **Removals prüfen:** Jede Datei aus dem letzten Release, die im neuen Paket fehlt (z. B. `mod-1.0.jar` → `mod-1.1.jar`),
   muss mit ihrem **alten SHA256** unter `Removals` stehen. Sonst bleibt die alte Jar liegen, und es gibt doppelte Mod-IDs.
4. **Prüfen:** `release.json` gegen die Launcher-Regeln prüfen: Schema 1, Minecraft `1.21.8`, Version `x.y.z` und höher als `latest`,
   `ZipUrl` = `.../releases/download/v<version>/ChillZone-Paket-<version>.zip`, `ZipSha256`/`ZipSize` passen zum ZIP,
   Pfade nur `mods|resourcepacks|shaderpacks/<datei>`, keine Duplikate, jede `Url` auf `https://cdn.modrinth.com/`.
   Bei Code-Änderungen am Launcher zusätzlich `--selftest` beider EXEs laufen lassen.
5. **Veröffentlichen:**
   ```
   gh release create v<version> ChillZone-Paket-<version>.zip release.json -R linox55555-prog/chillzone-updates --title "Chill Zone Paket <version>" --notes "..."
   ```
6. **Online nachprüfen:** `release.json` über die `latest`-URL und das ZIP über HTTPS herunterladen und vergleichen:
   SHA256 und Größe des ZIP gleich `ZipSha256`/`ZipSize`, die heruntergeladene `release.json` gleich der lokalen.

## Mehrere Updates / Versionen überspringen

Der Launcher wendet **nur das neueste `release.json`** an. Wer Versionen überspringt (z. B. 0.5.0 → 0.5.3), bekommt nur die Removals der neuesten Version.

- **Removals sind kumulativ.** Jede neue `release.json` muss alle Removals aller früheren Releases weiterführen, solange die alte Datei
  bei jemandem noch liegen könnte. Ausnahme: Die Datei ist in der neuen Version wieder unter **gleichem Pfad** in `Files` enthalten.
  Der Builder übernimmt die Removals früherer Releases automatisch (per `gh` aus allen Releases, sonst aus `latest`),
  das Prüfskript meldet fehlende.
- **Immer nur EINE KI baut und veröffentlicht.** Vorher mit `gh release list -R linox55555-prog/chillzone-updates` die aktuelle Version prüfen.
  Die neue Version muss höher sein.
- **Keine Releases ersetzen oder löschen.**

## Regeln

- Nie fremde ARR/NC/Polyform-Mods oder -Packs ins ZIP oder in dieses Repo. Fremde Dateien kommen nur per Modrinth-`Url`.
- Nicht öffentliche Testpakete und interne Notizen kommen in kein Release.
- Nie ein Release löschen, ersetzen oder Assets überschreiben. Bei Fehlern eine neue, höhere Version anlegen.
- Änderungen am Launcher-Programm selbst werden nicht über diesen Feed verteilt, sondern als neue EXE.
- In diesem Repo liegen keine Mods, nur Code und Listen.

## Inhalt

- [`werkzeug/`](werkzeug/): `build_release.py` (Builder), `mod-lizenzen.csv` (Herkunft und Lizenz jeder Datei), eigene README.
