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
        r = requests.get(asset['browser_download_url'], timeout=20)
        with zipfile.ZipFile(BytesIO(r.content)) as z:
            content_pool = ""
            for file_name in z.namelist():
                if 'build.prop' in file_name:
                    with z.open(file_name) as f:
                        content_pool += f.read().decode('utf-8', errors='ignore') + "\n"

            fp = extract_value(content_pool, SCHEMA["FINGERPRINT"])

            # If it's a valid certified fingerprint and NOT in our database, grab it.
            if fp and fp not in used_fps:
                api = extract_value(content_pool, SCHEMA["API_LEVEL"])
                sdk_val = int(api) if api.isdigit() else 25
                
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
                return (fp, asset['name'].replace('.zip', '.json'), pif_data)
    except:
        pass
    return None

def run():
    os.makedirs(PIF_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE): open(DB_FILE, 'w').close()

    with open(DB_FILE, 'r') as f:
        used_fps = {line.strip() for line in f if line.strip()}

    print(f"🕵️ Bruteforce Scan Started. Database: {len(used_fps)}")
    
    all_assets = []
    # Exhaustive search through the last 5 pages (500 assets)
    for page in range(1, 6):
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
            fp, filename, data = res
            with open(os.path.join(PIF_DIR, filename), 'w') as out:
                json.dump(data, out, indent=2)
            db.write(fp + "\n")
            print(f"💎 New Discovery: {filename}")
            new_count += 1

    print(f"🏁 Finished. Z E U S B O T added {new_count} fingerprints.")

if __name__ == "__main__":
    run()
