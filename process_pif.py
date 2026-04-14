import os
import re
import json
import zipfile
import requests
import concurrent.futures
from io import BytesIO

# --- CONFIGURATION ---
BASE_PIF_DIR = './pif_library'
DB_FILE = './used_fingerprints.txt'
SOURCE_REPO = "Pixel-Props/build.prop"

# Keywords for all devices getting updates + Beta/QPR identifiers
BETA_KEYWORDS = ["beta", "dev", "test-keys", "qpr", "experimental", "baklava"]
DEVICE_KEYWORDS = [
    "tokay", "komodo", "caiman", "comet", # Pixel 9 Series
    "shiba", "husky", "akita",           # Pixel 8 Series
    "lynx", "cheetah", "panther",        # Pixel 7 Series
    "bluejay", "oriole", "raven"          # Pixel 6 Series
]

SCHEMA = {
    "BRAND": [r"ro\.product\.brand=(.*)"],
    "MANUFACTURER": [r"ro\.product\.manufacturer=(.*)"],
    "MODEL": [r"ro\.product\.model=(.*)"],
    "PRODUCT": [r"ro\.product\.name=(.*)"],
    "DEVICE": [r"ro\.product\.device=(.*)"],
    "FINGERPRINT": [r"ro\.build\.fingerprint=(.*)", r"ro\.system\.build\.fingerprint=(.*)"],
    "ID": [r"ro\.build\.id=(.*)"],
    "TYPE": [r"ro\.build\.type=(.*)"],
    "TAGS": [r"ro\.build\.tags=(.*)"],
    "SECURITY_PATCH": [r"ro\.build\.version\.security_patch=(.*)"],
    "API_LEVEL": [r"ro\.build\.version\.sdk=(.*)", r"ro\.product\.first_api_level=(.*)"]
}

def extract_value(data, patterns):
    for pattern in patterns:
        match = re.search(pattern, data)
        if match:
            return match.group(1).strip()
    return ""

def process_asset(asset, used_fps):
    if not asset['name'].endswith('.zip'): return None
    try:
        r = requests.get(asset['browser_download_url'], timeout=30)
        with zipfile.ZipFile(BytesIO(r.content)) as z:
            content_pool = ""
            for file_name in z.namelist():
                if 'build.prop' in file_name:
                    with z.open(file_name) as f:
                        content_pool += f.read().decode('utf-8', errors='ignore') + "\n"

            fp = extract_value(content_pool, SCHEMA["FINGERPRINT"])
            if not fp or fp in used_fps: return None

            api = extract_value(content_pool, SCHEMA["API_LEVEL"])
            sdk_val = int(api) if api.isdigit() else 25
            
            # Determine if Beta or Released
            is_beta = any(word in fp.lower() or word in asset['name'].lower() for word in BETA_KEYWORDS)
            category = "beta" if is_beta else "released"
            
            # Use Device and Build ID for a clean filename
            dev_name = extract_value(content_pool, SCHEMA["DEVICE"]) or "unknown"
            build_id = extract_value(content_pool, SCHEMA["ID"]) or "build"
            filename = f"{dev_name}_{build_id}.json"

            pif_data = {
                "BRAND": extract_value(content_pool, SCHEMA["BRAND"]),
                "MANUFACTURER": extract_value(content_pool, SCHEMA["MANUFACTURER"]),
                "MODEL": extract_value(content_pool, SCHEMA["MODEL"]),
                "PRODUCT": extract_value(content_pool, SCHEMA["PRODUCT"]),
                "DEVICE": dev_name,
                "FINGERPRINT": fp,
                "ID": build_id,
                "TYPE": extract_value(content_pool, SCHEMA["TYPE"]) or "user",
                "TAGS": extract_value(content_pool, SCHEMA["TAGS"]) or "release-keys",
                "VERSION:SECURITY_PATCH": extract_value(content_pool, SCHEMA["SECURITY_PATCH"]),
                "VERSION:API_LEVEL": sdk_val,
                "VERSION:SDK_LEVEL": sdk_val
            }
            return (fp, category, filename, pif_data)
    except: pass
    return None

def run():
    # Setup Directory Structure
    for cat in ["beta", "released"]:
        os.makedirs(os.path.join(BASE_PIF_DIR, cat), exist_ok=True)
    
    if not os.path.exists(DB_FILE): open(DB_FILE, 'w').close()
    with open(DB_FILE, 'r') as f:
        used_fps = {line.strip() for line in f if line.strip()}

    print(f"🕵️ Z E U S B O T starting organized crawl. Known: {len(used_fps)}")
    
    all_assets = []
    for page in range(1, 11): # Deep history crawl
        api_url = f"https://api.github.com/repos/{SOURCE_REPO}/releases?per_page=100&page={page}"
        res = requests.get(api_url).json()
        if not res or not isinstance(res, list): break
        for release in res:
            all_assets.extend(release.get('assets', []))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda a: process_asset(a, used_fps), all_assets))

    new_count = 0
    with open(DB_FILE, 'a') as db:
        for res in filter(None, results):
            fp, category, filename, data = res
            target_path = os.path.join(BASE_PIF_DIR, category, filename)
            
            with open(target_path, 'w') as out:
                json.dump(data, out, indent=2)
            
            db.write(fp + "\n")
            print(f"✅ [{category.upper()}] Saved: {filename}")
            new_count += 1

    print(f"🏁 Done. Sorted {new_count} new fingerprints into their folders.")

if __name__ == "__main__":
    run()
