import os
import re
import json
import zipfile
import requests
import concurrent.futures
from io import BytesIO
from datetime import datetime

# --- CONFIGURATION ---
BASE_PIF_DIR = './pif_library'
DB_FILE = './used_fingerprints.txt'
# Current High-Value Targets for April 2026
TARGET_PATCH = "2026-04-05"
BETA_BUILD_ID = "CP21.260330.008" # Android 17 Beta 4

SOURCES = [
    {"repo": "Pixel-Props/build.prop", "type": "zip"},
    {"repo": "chiteroman/PlayIntegrityFix", "type": "zip"},
    {"repo": "TheMlgPr0/certified-fingerprints", "type": "raw"},
    {"repo": "farman13/PIF", "type": "json"},
    {"repo": "TheFreeman193/PIFS", "type": "zip"},
    {"repo": "daboynb/autojson", "type": "raw"},
    {"repo": "MeowDump/Integrity-Box", "type": "json"},
    {"repo": "BasGame1/Pixelify-Next", "type": "zip"}
]

BETA_KEYWORDS = ["beta", "dev", "test-keys", "qpr", "experimental", "baklava", "vanilla", "canary"]

def get_patch_from_fp(fp):
    match = re.search(r':(\d{4}-\d{2}-\d{2}):', fp)
    return match.group(1) if match else None

def parse_props(content, source_name):
    # protocol: JSON, Prop, or Raw
    is_json = content.strip().startswith('{')
    try:
        if is_json:
            j = json.loads(content)
            fp = j.get("FINGERPRINT") or j.get("ro.build.fingerprint")
            if not fp: return None
            pif = {
                "BRAND": j.get("BRAND") or j.get("ro.product.brand", "google"),
                "MANUFACTURER": j.get("MANUFACTURER") or "Google",
                "MODEL": j.get("MODEL") or "Pixel",
                "PRODUCT": j.get("PRODUCT") or "unknown",
                "DEVICE": j.get("DEVICE") or j.get("ro.product.device", "unknown"),
                "FINGERPRINT": fp,
                "ID": j.get("ID") or j.get("ro.build.id", "unknown"),
                "VERSION:SECURITY_PATCH": j.get("VERSION:SECURITY_PATCH") or get_patch_from_fp(fp),
                "VERSION:API_LEVEL": int(j.get("VERSION:API_LEVEL") or j.get("SDK_INT") or 32)
            }
        else:
            # Prop Regex Extraction
            fp_match = re.search(r"ro\.build\.fingerprint=(.*)", content)
            if not fp_match: return None
            fp = fp_match.group(1).strip()
            pif = {
                "BRAND": "google", "MANUFACTURER": "Google", "FINGERPRINT": fp,
                "DEVICE": (re.search(r"ro\.product\.device=(.*)", content) or re.search(r"ro\.product\.system\.device=(.*)", content)).group(1).strip(),
                "ID": re.search(r"ro\.build\.id=(.*)", content).group(1).strip(),
                "VERSION:SECURITY_PATCH": get_patch_from_fp(fp),
                "VERSION:API_LEVEL": 32
            }
        
        pif["VERSION:SDK_LEVEL"] = pif["VERSION:API_LEVEL"]
        pif["_zeus_meta"] = {"sync_date": datetime.now().strftime('%Y-%m-%d'), "source": source_name}
        
        # Determine Category
        is_beta = any(word in fp.lower() or word in source_name.lower() or BETA_BUILD_ID in fp for word in BETA_KEYWORDS)
        category = "beta" if is_beta else "released"
        
        # Logic Gate: Only save if it's the current working cycle (2026)
        if TARGET_PATCH in pif["VERSION:SECURITY_PATCH"] or BETA_BUILD_ID in pif["ID"]:
            return (fp, category, f"{pif['DEVICE']}_{pif['ID']}.json".replace("/", "_"), pif)
        return None
    except: return None

def process_source(s):
    found = []
    try:
        # Step 1: Check Releases
        rel_res = requests.get(f"https://api.github.com/repos/{s['repo']}/releases").json()
        for r in rel_res[:3]:
            for asset in r.get('assets', []):
                if any(asset['name'].endswith(ext) for ext in ['.zip', '.json', '.prop']):
                    resp = requests.get(asset['browser_download_url'])
                    if s['type'] == "zip":
                        with zipfile.ZipFile(BytesIO(resp.content)) as z:
                            for f_name in z.namelist():
                                if f_name.endswith(('.json', '.prop')):
                                    with z.open(f_name) as f:
                                        res = parse_props(f.read().decode('utf-8', errors='ignore'), asset['name'])
                                        if res: found.append(res)
                    else:
                        res = parse_props(resp.text, asset['name'])
                        if res: found.append(res)

        # Step 2: Deep Branch Crawl (For Leaks)
        branch = requests.get(f"https://api.github.com/repos/{s['repo']}").json().get('default_branch', 'main')
        tree = requests.get(f"https://api.github.com/repos/{s['repo']}/git/trees/{branch}?recursive=1").json()
        for item in tree.get('tree', []):
            if item['path'].endswith(('.json', '.prop')) and "pif" in item['path'].lower():
                raw_url = f"https://raw.githubusercontent.com/{s['repo']}/{branch}/{item['path']}"
                res = parse_props(requests.get(raw_url).text, item['path'])
                if res: found.append(res)
    except: pass
    return found

def run():
    for cat in ["beta", "released", "ultimate"]: os.makedirs(os.path.join(BASE_PIF_DIR, cat), exist_ok=True)
    if not os.path.exists(DB_FILE): open(DB_FILE, 'w').close()
    with open(DB_FILE, 'r') as f: used_fps = {line.strip() for line in f if line.strip()}

    print(f"🕵️ Z E U S B O T: April 2026 Deep Audit across {len(SOURCES)} sources...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(process_source, SOURCES))

    new_count = 0
    with open(DB_FILE, 'a') as db:
        for source_result in results:
            for res in source_result:
                fp, cat, fname, data = res
                if fp not in used_fps:
                    # Final Check: If it matches 2026-04-05, put it in 'ultimate'
                    if TARGET_PATCH in data["VERSION:SECURITY_PATCH"]: cat = "ultimate"
                    
                    with open(os.path.join(BASE_PIF_DIR, cat, fname), 'w') as out:
                        json.dump(data, out, indent=2)
                    db.write(fp + "\n")
                    used_fps.add(fp)
                    new_count += 1
                    print(f"💎 [ULTIMATE] Captured: {fname}")

    print(f"🏁 Audit Complete. {new_count} new fingerprints secured.")

if __name__ == "__main__":
    run()
