import os
import re
import json
import zipfile
import requests
import concurrent.futures
from io import BytesIO

PIF_DIR = './pif_library'
DB_FILE = './used_fingerprints.txt'
SOURCE_REPO = "Pixel-Props/build.prop"

# Keywords that define the "Unburned Beta" target
BETA_TARGETS = ["beta", "dev", "test-keys", "qpr", "tokay", "komodo", "caiman", "shiba", "husky"]

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
    if not asset['name'].endswith('.zip'):
        return None
    try:
        r = requests.get(asset['browser_download_url'], timeout=30)
        with zipfile.ZipFile(BytesIO(r.content)) as z:
            content_pool = ""
            for file_name in z.namelist():
                if 'build.prop' in file_name:
                    with z.open(file_name) as f:
                        content_pool += f.read().decode('utf-8', errors='ignore') + "\n"

            fp = extract_value(content_pool, SCHEMA["FINGERPRINT"])
            if not fp or fp in used_fps:
                return None

            api = extract_value(content_pool, SCHEMA["API_LEVEL"])
            sdk_val = int(api) if api.isdigit() else 25
            
            # Check if this is a Beta/Dev build
            is_beta = any(word in fp.lower() or word in asset['name'].lower() for word in BETA_TARGETS)
            
            pif_data = {
                "BRAND": extract_value(content_pool, SCHEMA["BRAND"]),
                "MANUFACTURER": extract_value(content_pool, SCHEMA["MANUFACTURER"]),
                "MODEL": extract_value(content_pool, SCHEMA["MODEL"]),
                "PRODUCT": extract_value(content_pool, SCHEMA["PRODUCT"]),
                "DEVICE": extract_value(content_pool, SCHEMA["DEVICE"]),
                "FINGERPRINT": fp,
                "ID": extract_value(content_pool, SCHEMA["ID"]),
                "TYPE": extract_value(content_pool, SCHEMA["TYPE"]) or "user",
                "TAGS": extract_value(content_pool, SCHEMA["TAGS"]) or "release-keys",
                "VERSION:SECURITY_PATCH": extract_value(content_pool, SCHEMA["SECURITY_PATCH"]),
                "VERSION:API_LEVEL": sdk_val,
                "VERSION:SDK_LEVEL": sdk_val
            }
            return (fp, asset['name'].replace('.zip', '.json'), pif_data, is_beta)
    except:
        pass
    return None

def run():
    os.makedirs(PIF_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE): open(DB_FILE, 'w').close()

    with open(DB_FILE, 'r') as f:
        used_fps = {line.strip() for line in f if line.strip()}

    print(f"🕵️ Deep Scan: Filtering for Beta vs Release...")
    
    all_assets = []
    # Scrape 10 pages for maximum history
    for page in range(1, 11):
        api_url = f"https://api.github.com/repos/{SOURCE_REPO}/releases?per_page=100&page={page}"
        res = requests.get(api_url).json()
        if not res or not isinstance(res, list): break
        for release in res:
            all_assets.extend(release.get('assets', []))

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda a: process_asset(a, used_fps), all_assets))

    # Separation logic: Prioritize Betas first
    valid_results = [r for r in results if r is not None]
    betas = [r for r in valid_results if r[3]]
    releases = [r for r in valid_results if not r[3]]

    new_count = 0
    with open(DB_FILE, 'a') as db:
        # Process Betas first to ensure they aren't missed
        for fp, filename, data, _ in (betas + releases):
            with open(os.path.join(PIF_DIR, filename), 'w') as out:
                json.dump(data, out, indent=2)
            db.write(fp + "\n")
            status = "🔥 BETA" if _ else "📦 RELEASE"
            print(f"Captured [{status}]: {filename}")
            new_count += 1

    print(f"🏁 Total New PIFs in Z E U S B O T vault: {new_count}")

if __name__ == "__main__":
    run()
