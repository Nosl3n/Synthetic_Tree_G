#!/usr/bin/env bash
# Descarga los QSM de Barro Colorado Island (Krishna Moorthy et al. 2022, Zenodo 6981485, CC BY 4.0).
# Destino: data/bci_zenodo_6981485/QSMs/*.mat (201 árboles, 37 MB).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DST="$ROOT/data/bci_zenodo_6981485"
mkdir -p "$DST"
cd "$DST"
if [ ! -d QSMs ] || [ "$(ls QSMs/*.mat 2>/dev/null | wc -l)" -lt 201 ]; then
    curl -L --fail -o QSMs.zip "https://zenodo.org/api/records/6981485/files/QSMs.zip/content"
    python3 - <<'PY'
import hashlib, json, urllib.request
rec = json.load(urllib.request.urlopen("https://zenodo.org/api/records/6981485"))
md5 = {f["key"]: f["checksum"].split(":")[1] for f in rec["files"]}["QSMs.zip"]
got = hashlib.md5(open("QSMs.zip", "rb").read()).hexdigest()
assert got == md5, f"MD5 distinto: {got} != {md5}"
print("MD5 OK", md5)
PY
    unzip -q -o QSMs.zip
    rm QSMs.zip
fi
echo "QSMs: $(ls QSMs/*.mat | wc -l) archivos en $DST/QSMs"
