"""Baut ChillZone-Paket-<version>.zip + release.json (Engine.cs Schema 1, mit Url-Feld) und mod-lizenzen.csv.

Regeln (Entscheidung 18.11.):
  * Fremde Dateien werden NICHT selbst verteilt. Liegt die Datei (gleicher SHA1) auf Modrinth,
    bekommt sie im Manifest eine Url auf https://cdn.modrinth.com und fehlt im ZIP.
  * Ohne Modrinth-Treffer kommen ins ZIP nur eigene Dateien (auenpfad-*, m0xx-*, Auenpfad-*-Packs)
    oder Dateien mit freier Lizenz (MIT, Apache, LGPL, GPL, CC0).
  * Alles andere wird weggelassen und im Bericht aufgefuehrt.
  * Removals: alte Dateinamen aus frueheren Kollegen-Paketen (alte-pakete-scan.json), die es nicht mehr gibt.

Nur lesend gegenueber Mittelerde\\Client. Schreibt ausschliesslich in diesen Ordner.
Aufruf:  python -I build_release.py [version]
"""
from pathlib import Path
import csv, hashlib, io, json, re, sys, time, urllib.parse, urllib.request, urllib.error, zipfile

VERSION = sys.argv[1] if len(sys.argv) > 1 else "0.5.0"
HERE = Path(__file__).resolve().parent
MITTELERDE = HERE.parent.parent
CLIENT = MITTELERDE / "Client"
SERVER_MODS = MITTELERDE / "Server" / "mods"
ZIP_NAME = f"ChillZone-Paket-{VERSION}.zip"
ZIP_URL = f"https://github.com/linox55555-prog/chillzone-updates/releases/download/v{VERSION}/{ZIP_NAME}"
FIXED_TIME = (2026, 11, 18, 0, 0, 0)
UA = "ChillZone-Launcher-Build"
CDN = "cdn.modrinth.com"
OLD_SCAN = HERE / "alte-pakete-scan.json"   # erzeugt von werkzeug/scan_old_packages.py
LOCAL_HASH_DIRS = ["Downloads", "Sicherungen", "Tests"]

SKIP_MODS = {
    "chillzone-autojoin-0.3.0.jar": "bringt der Launcher selbst mit",
    "mira-admin-key-f7-1.0.0-test1.jar": "Admin-Testwerkzeug (F7, nur lokaler Testserver), nicht fuer Mitspieler",
}
SKIP_PACK_DIRS = {"Auenland-3D-Vorschau": "Vorschau-Ordner, in options.txt nicht aktiv"}
OWN_RX = re.compile(r"^(auenpfad-|m0\d\d-)", re.I)
FREE_RX = re.compile(r"\b(MIT|Apache|LGPL|GPL|CC0)\b", re.I)
NONFREE_RX = re.compile(r"(ARR|All Rights Reserved|-NC|Polyform)", re.I)


def sha(data: bytes, algo="sha256"):
    return hashlib.new(algo, data).hexdigest()


def zip_folder(folder: Path) -> bytes:
    """Ordner-Ressourcenpaket deterministisch als ZIP (gleiche Bytes bei gleichem Inhalt)."""
    assert (folder / "pack.mcmeta").is_file(), f"kein pack.mcmeta in {folder}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(folder.rglob("*"), key=lambda x: x.relative_to(folder).as_posix()):
            if p.is_file():
                info = zipfile.ZipInfo(p.relative_to(folder).as_posix(), FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, p.read_bytes(), compresslevel=6)
    return buf.getvalue()


def lic_files(names):
    return [n for n in names if re.search(r"(licen[cs]e|copying|credits|readme|terms)", n.rsplit("/", 1)[-1], re.I)
            and n.count("/") <= 1]


def jar_info(data: bytes):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        j = json.loads(z.read("fabric.mod.json").decode("utf-8-sig"), strict=False)
        extra = lic_files(z.namelist())
    lic = j.get("license", "")
    lic = ", ".join(lic) if isinstance(lic, list) else str(lic or "")
    contact = j.get("contact") or {}
    link = contact.get("homepage") or contact.get("sources") or contact.get("issues") or ""
    return {"id": j.get("id", ""), "name": j.get("name", ""), "version": str(j.get("version", "")),
            "license": lic, "link": link, "environment": j.get("environment", "*"),
            "license_files": ";".join(extra[:4])}


def pack_info(data: bytes):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist(); desc = ""
        if "pack.mcmeta" in names:
            try:
                d = json.loads(z.read("pack.mcmeta").decode("utf-8-sig"), strict=False).get("pack", {}).get("description", "")
                desc = d if isinstance(d, str) else json.dumps(d, ensure_ascii=False)
            except Exception as e:
                desc = f"(pack.mcmeta unlesbar: {e})"
        files = lic_files(names); lic_text = ""
        for n in files:
            if re.search(r"licen[cs]e", n, re.I):
                lic_text = z.read(n)[:300].decode("utf-8", "replace").replace("\r", " ").replace("\n", " ").strip()
                break
    return desc, files, lic_text


def modrinth_lookup(sha1: str):
    """Liefert (url, version_info) fuer die Datei mit genau diesem SHA1 oder (None, None)."""
    req = urllib.request.Request(f"https://api.modrinth.com/v2/version_file/{sha1}?algorithm=sha1",
                                 headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                v = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, None
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt); continue
            raise
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"Modrinth nicht erreichbar fuer {sha1}")
    files = [f for f in v.get("files", []) if f.get("hashes", {}).get("sha1", "").lower() == sha1.lower()]
    if not files:
        return None, None
    f = next((x for x in files if x.get("primary")), files[0])
    u = urllib.parse.urlsplit(f["url"])
    if u.scheme != "https" or u.hostname != CDN or u.username or (u.port not in (None, 443)):
        raise RuntimeError(f"Modrinth-URL nicht auf {CDN}: {f['url']}")
    return f["url"], {"project_id": v.get("project_id"), "version_id": v.get("id"), "version_number": v.get("version_number")}


def old_sha256(path: str, entry: dict):
    """SHA256 einer alten Datei: aus dem Scan, sonst lokale Kopie mit passendem SHA1 suchen."""
    if len(entry["sha256"]) == 1:
        return entry["sha256"][0], "Paketinhalt"
    if len(entry["sha256"]) > 1:
        return None, "mehrere Staende mit gleichem Namen"
    name = path.split("/", 1)[1]
    for d in LOCAL_HASH_DIRS:
        for p in (MITTELERDE / d).rglob(name):
            b = p.read_bytes()
            if sha(b, "sha1") in entry["sha1"]:
                return sha(b), f"lokale Kopie {p.relative_to(MITTELERDE)}"
    return None, "kein SHA256 ermittelbar"


def main():
    server_hashes = {sha(p.read_bytes()) for p in SERVER_MODS.glob("*.jar")}
    server_names = {p.name for p in SERVER_MODS.glob("*.jar")}
    candidates, skipped = [], []

    for p in sorted((CLIENT / "mods").iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        if p.name in SKIP_MODS:
            skipped.append({"Pfad": f"mods/{p.name}", "Grund": SKIP_MODS[p.name]}); continue
        if p.suffix.lower() != ".jar":
            skipped.append({"Pfad": f"mods/{p.name}", "Grund": "keine .jar"}); continue
        data = p.read_bytes(); h = sha(data); info = jar_info(data)
        role = ("Server+Client (Server verlangt)" if h in server_hashes else
                "Server hat ANDERE Version!" if p.name in server_names else "nur Client")
        candidates.append({"path": f"mods/{p.name}", "data": data, "role": role, "name": info["name"],
                           "modid": info["id"], "version": info["version"], "license": info["license"],
                           "link": info["link"], "license_files": info["license_files"], "note": ""})

    for kind in ("resourcepacks", "shaderpacks"):
        for p in sorted((CLIENT / kind).iterdir(), key=lambda x: x.name.lower()):
            note = ""
            if p.is_dir():
                if p.name in SKIP_PACK_DIRS:
                    skipped.append({"Pfad": f"{kind}/{p.name}/", "Grund": SKIP_PACK_DIRS[p.name]}); continue
                data = zip_folder(p); name = p.name + ".zip"
                note = "aus Ordner gepackt (Name wie im M054-Kollegenpaket)"
            elif p.suffix.lower() == ".zip":
                data = p.read_bytes(); name = p.name
            else:
                skipped.append({"Pfad": f"{kind}/{p.name}", "Grund": "Einstellungs-/Sicherungsdatei, nicht updatefaehig"}); continue
            desc, files, lic_text = pack_info(data)
            candidates.append({"path": f"{kind}/{name}", "data": data, "role": "nur Client", "name": desc[:120],
                               "modid": "", "version": "", "license": lic_text[:200], "link": "",
                               "license_files": ";".join(files[:4]), "note": note})

    included, rows = [], []
    for c in candidates:
        fname = c["path"].split("/", 1)[1]
        url, vinfo = modrinth_lookup(sha(c["data"], "sha1"))
        if url:
            source, reason = "Modrinth", f"Modrinth-Treffer (Version {vinfo['version_number']})"
        elif OWN_RX.match(fname):
            source, reason = "ZIP", "eigene Datei (Projekt)"
        elif c["license"] and FREE_RX.search(c["license"]) and not NONFREE_RX.search(c["license"]):
            source, reason = "ZIP", f"freie Lizenz ({c['license'][:40]})"
        else:
            source = "WEGGELASSEN"
            reason = f"kein Modrinth-Treffer, Lizenz: {c['license'][:60] or 'keine Angabe'}"
            skipped.append({"Pfad": c["path"], "Grund": reason})
        if source != "WEGGELASSEN":
            included.append({"path": c["path"], "data": c["data"], "url": url or ""})
        rows.append({"Pfad": c["path"], "Quelle": source, "Grund": reason, "Groesse": len(c["data"]),
                     "SHA256": sha(c["data"]), "SHA1": sha(c["data"], "sha1"), "Rolle": c["role"],
                     "Name": c["name"], "ModId": c["modid"], "Version": c["version"],
                     "Lizenz": c["license"] or "(keine Angabe)", "Link": c["link"], "ModrinthUrl": url or "",
                     "Lizenzdateien": c["license_files"], "Hinweis": c["note"]})

    new_paths = {f["path"].lower() for f in included}
    server_missing = [r["Pfad"] for r in rows if r["Rolle"].startswith("Server") and r["Quelle"] == "WEGGELASSEN"]

    # Removals aus frueheren Kollegen-Paketen
    removals, removal_problems = [], []
    old = json.loads(OLD_SCAN.read_text(encoding="utf-8"))
    for path, entry in sorted(old.items()):
        if path.lower() in new_paths:
            continue
        h, how = old_sha256(path, entry)
        if h:
            removals.append({"Path": path, "OldSha256": h, "_herkunft": how, "_quellen": len(entry["sources"])})
        else:
            removal_problems.append({"Path": path, "Problem": how})

    with open(HERE / "mod-lizenzen.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader(); w.writerows(rows)

    zpath = HERE / ZIP_NAME
    in_zip = [f for f in included if not f["url"]]
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for f in in_zip:
            info = zipfile.ZipInfo(f["path"], FIXED_TIME); info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f["data"], compresslevel=6)
    with zipfile.ZipFile(zpath) as z:
        assert z.testzip() is None
        assert sorted(z.namelist()) == sorted(f["path"] for f in in_zip)
    zbytes = zpath.read_bytes()

    def file_entry(f):
        e = {"Path": f["path"], "Sha256": sha(f["data"]), "Size": len(f["data"])}
        if f["url"]:
            e["Url"] = f["url"]
        return e

    release = {"Schema": 1, "Version": VERSION, "Minecraft": "1.21.8", "ZipUrl": ZIP_URL,
               "ZipSha256": sha(zbytes), "ZipSize": len(zbytes),
               "Files": [file_entry(f) for f in included],
               "Removals": [{"Path": r["Path"], "OldSha256": r["OldSha256"]} for r in removals]}
    (HERE / "release.json").write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {"version": VERSION, "zip": ZIP_NAME, "zipSize": len(zbytes), "zipSha256": sha(zbytes),
              "filesTotal": len(included), "filesFromModrinth": [f["path"] for f in included if f["url"]],
              "filesInZip": [{"Pfad": r["Pfad"], "Grund": r["Grund"]} for r in rows if r["Quelle"] == "ZIP"],
              "skipped": skipped, "serverRequiredButSkipped": server_missing,
              "removals": removals, "removalProblems": removal_problems}
    (HERE / "BUILD-REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
