import os
import re
import json
import zipfile
import requests
import concurrent.futures
from io import BytesIO
from datetime import datetime

# --- SETTINGS ---
BASE_PIF_DIR = './pif_library'
DB_FILE = './used_fingerprints.txt'

# GLOBAL SOURCES 2026: The Complete Collection
SOURCES = [
    {"repo": "Pixel-Props/build.prop", "type": "zip"},
    {"repo": "chiteroman/PlayIntegrityFix", "type": "zip"},
    {"repo": "TheMlgPr0/certified-fingerprints", "type": "raw"},
    {"repo": "TheFreeman193/PIFS", "type": "zip"},
    {"repo": "daboynb/build.prop", "type": "zip"},
    {"repo": "farman13/PIF", "type": "json"},             # Farmaan's dedicated PIF source
    {"repo": "osm0sis/PlayIntegrityFork", "type": "raw"}, # Legacy and universal recognizer props
    {"repo": "LineageOS/android_vendor_lineage", "type": "raw"},
    {"repo": "MeowDump/Integrity-Box", "type": "json"},   # High-integrity modern props
    {"repo": "BasGame1/Pixelify-Next", "type": "zip"}
]

BETA_KEYWORDS = ["beta", "dev", "test-keys", "qpr", "experimental", "baklava", "vanilla", "canary"]

SCHEMA = {
    "BRAND": [r"ro\.product\.brand=(.*)"],
    "MANUFACTURER": [r"ro\.product\.manufacturer=(.*)"],
    "MODEL": [r"ro\.product\.model=(.*)"],
    "PRODUCT": [r"ro\.product\.name=(.*)"],
    "DEVICE": [r"ro\.product\.device=(.*)"],
    "FINGERPRINT": [r"ro\.build\.fingerprint=(.*)", r"ro\.system\.build\.fingerprint=(.*)"],
    "ID": [r"ro\.build\.id=(.*)"],
    "SECURITY_PATCH": [r"ro\.build\.version\.security_patch=(.*)"],
    "API_LEVEL": [r"ro\.build\.version\.sdk=(.*)", r"ro\.product\.first_api_level=(.*)"]
}

def get_patch_from_fp(fp):
    match = re.search(r':(\d{4}-\d{2}-\d{2}):', fp)
    return match.group(1) if match else None

def parse_props(content, source_name):
    # JSON-Direct Protocol (Farmaan, MeowDump, etc.)
    if content.strip().startswith('{'):
        try:
            j = json.loads(content)
            fp = j.get("FINGERPRINT") or j.get("ro.build.fingerprint")
            if not fp: return None
            pif_data = {
                "BRAND": j.get("BRAND") or j.get("ro.product.brand", ""),
                "MANUFACTURER": j.get("MANUFACTURER") or j.get("ro.product.manufacturer", ""),
                "MODEL": j.get("MODEL") or j.get("ro.product.model", ""),
                "PRODUCT": j.get("PRODUCT") or j.get("ro.product.name", ""),
                "DEVICE": j.get("DEVICE") or j.get("ro.product.device", "unknown"),
                "FINGERPRINT": fp,
                "ID": j.get("ID") or j.get("ro.build.id", "build"),
                "VERSION:SECURITY_PATCH": j.get("VERSION:SECURITY_PATCH", get_patch_from_fp(fp)),
                "VERSION:API_LEVEL": int(j.get("VERSION:API_LEVEL", 25))
            }
        except: return None
    else:
        # Build.Prop Protocol
        fp = extract_value(content, SCHEMA["FINGERPRINT"])
        if not fp: return None
        pif_data = {
            "BRAND": extract_value(content, SCHEMA["BRAND"]),
            "MANUFACTURER": extract_value(content, SCHEMA["MANUFACTURER"]),
            "MODEL": extract_value(content, SCHEMA["MODEL"]),
            "PRODUCT": extract_value(content, SCHEMA["PRODUCT"]),
            "DEVICE": extract_value(content, SCHEMA["DEVICE"]) or "unknown",
            "FINGERPRINT": fp,
            "ID": extract_value(content, SCHEMA["ID"]) or "build",
            "VERSION:SECURITY_PATCH": get_patch_from_fp(fp) or extract_value(content, SCHEMA["SECURITY_PATCH"]),
            "VERSION:API_LEVEL": int(extract_value(content, SCHEMA["API_LEVEL"]) or 25)
        }
    
    pif_data["VERSION:SDK_LEVEL"] = pif_data["VERSION:API_LEVEL"]
    pif_data["_zeus_meta"] = {"sync_date": datetime.now().strftime('%Y-%m-%d'), "source": source_name}
    category = "beta" if any(word in fp.lower() for word in BETA_KEYWORDS) else "released"
    return (fp, category, f"{pif_data['DEVICE']}_{pif_data['ID']}.json", pif_data)

def extract_value(data, patterns):
    for p in patterns:
        m = re.search(p, data)
        if m: return m.group(1).strip()
    return ""

def process_asset(url, name, s_type):
    try:
        r = requests.get(url, timeout=30)
        if s_type == "zip":
            with zipfile.ZipFile(BytesIO(r.content)) as z:
                pool = ""
                for f in z.namelist():
                    if any(f.endswith(ext) for ext in ['.prop', '.json']):
                        with z.open(f) as file: pool += file.read().decode('utf-8', errors='ignore') + "\n"
                return parse_props(pool, name)
        return parse_props(r.text, name)
    except: return None

def run():
    for cat in ["beta", "released"]: os.makedirs(os.path.join(BASE_PIF_DIR, cat), exist_ok=True)
    if not os.path.exists(DB_FILE): open(DB_FILE, 'w').close()
    with open(DB_FILE, 'r') as f: used_fps = {line.strip() for line in f if line.strip()}

    print(f"🚀 Z E U S B O T: Deep Scanning {len(SOURCES)} Global Sources...")
    tasks = []
    for s in SOURCES:
        try:
            res = requests.get(f"https://api.github.com/repos/{s['repo']}/releases?per_page=10").json()
            for release in res:
                for asset in release.get('assets', []):
                    tasks.append((asset['browser_download_url'], asset['name'], s['type']))
        except: continue

    new_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(process_asset, t[0], t[1], t[2]) for t in tasks]
        with open(DB_FILE, 'a') as db:
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res and res[0] not in used_fps:
                    fp, cat, fname, data = res
                    with open(os.path.join(BASE_PIF_DIR, cat, fname), 'w') as out:
                        json.dump(data, out, indent=2)
                    db.write(fp + "\n")
                    used_fps.add(fp)
                    new_count += 1
                    print(f"💎 Captured: {fname}")

    print(f"🏁 Sync Complete. Vault: {new_count} new entries.")

if __name__ == "__main__":
    run()
