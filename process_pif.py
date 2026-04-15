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
# Multiple high-quality sources for aggregation
SOURCES = [
    "Pixel-Props/build.prop",
    "chiteroman/PlayIntegrityFix"
]
BETA_KEYWORDS = ["beta", "dev", "test-keys", "qpr", "experimental", "baklava", "vanilla"]

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

def extract_value(data, patterns):
    for pattern in patterns:
        match = re.search(pattern, data)
        if match: return match.group(1).strip()
    return ""

def get_patch_from_fp(fp):
    """
    Intelligent Logic: Extracts the security patch date hidden inside 
    the fingerprint string (e.g., ...:user/release-keys:2024-03-05/...)
    """
    match = re.search(r':(\d{4}-\d{2}-\d{2}):', fp)
    return match.group(1) if match else None

def process_asset(asset_url, asset_name, used_fps):
    try:
        r = requests.get(asset_url, timeout=30)
        with zipfile.ZipFile(BytesIO(r.content)) as z:
            content_pool = ""
            for file_name in z.namelist():
                if file_name.endswith('.prop'):
                    with z.open(file_name) as f:
                        content_pool += f.read().decode('utf-8', errors='ignore') + "\n"

            fp = extract_value(content_pool, SCHEMA["FINGERPRINT"])
            if not fp or fp in used_fps: return None

            # --- INTELLIGENT CONSISTENCY CHECK ---
            reported_patch = extract_value(content_pool, SCHEMA["SECURITY_PATCH"])
            fp_patch = get_patch_from_fp(fp)
            # Use the fingerprint's internal date if they don't match (more reliable)
            final_patch = fp_patch if fp_patch else reported_patch

            is_beta = any(word in fp.lower() or word in asset_name.lower() for word in BETA_KEYWORDS)
            category = "beta" if is_beta else "released"
            
            api = extract_value(content_pool, SCHEMA["API_LEVEL"])
            sdk_val = int(api) if api.isdigit() else 25
            dev_name = extract_value(content_pool, SCHEMA["DEVICE"]) or "unknown"
            build_id = extract_value(content_pool, SCHEMA["ID"]) or "build"

            pif_data = {
                "BRAND": extract_value(content_pool, SCHEMA["BRAND"]),
                "MANUFACTURER": extract_value(content_pool, SCHEMA["MANUFACTURER"]),
                "MODEL": extract_value(content_pool, SCHEMA["MODEL"]),
                "PRODUCT": extract_value(content_pool, SCHEMA["PRODUCT"]),
                "DEVICE": dev_name,
                "FINGERPRINT": fp,
                "ID": build_id,
                "TYPE": "user",
                "TAGS": "release-keys",
                "VERSION:SECURITY_PATCH": final_patch,
                "VERSION:API_LEVEL": sdk_val,
                "VERSION:SDK_LEVEL": sdk_val,
                "_zeus_meta": {
                    "sync_date": datetime.now().strftime('%Y-%m-%d'),
                    "consistency_check": "fixed" if fp_patch and fp_patch != reported_patch else "pass"
                }
            }
            return (fp, category, f"{dev_name}_{build_id}.json", pif_data)
    except: pass
    return None

def run():
    for cat in ["beta", "released"]: os.makedirs(os.path.join(BASE_PIF_DIR, cat), exist_ok=True)
    if not os.path.exists(DB_FILE): open(DB_FILE, 'w').close()
    with open(DB_FILE, 'r') as f: used_fps = {line.strip() for line in f if line.strip()}

    all_assets = []
    for repo in SOURCES:
        print(f"🛰️ Z E U S B O T: Querying {repo}...")
        try:
            res = requests.get(f"https://api.github.com/repos/{repo}/releases?per_page=50").json()
            for release in res:
                for asset in release.get('assets', []):
                    if asset['name'].endswith('.zip'):
                        all_assets.append((asset['browser_download_url'], asset['name']))
        except: continue

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda a: process_asset(a[0], a[1], used_fps), all_assets))

    new_count = 0
    with open(DB_FILE, 'a') as db:
        for res in filter(None, results):
            fp, category, filename, data = res
            with open(os.path.join(BASE_PIF_DIR, category, filename), 'w') as out:
                json.dump(data, out, indent=2)
            db.write(fp + "\n")
            new_count += 1
    
    print(f"🏁 Vault Update Complete. Added {new_count} props.")

if __name__ == "__main__":
    run()
