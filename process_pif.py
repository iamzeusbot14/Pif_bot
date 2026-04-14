import os
import re
import json
import zipfile
import requests
from io import BytesIO
from datetime import datetime

PIF_DIR = './pif_library'
DB_FILE = './used_fingerprints.txt'
SOURCE_REPO = "Pixel-Props/build.prop"

# Target Beta/Dev builds specifically
BETA_KEYWORDS = ["beta", "dev", "test-keys", "experimental", "tokay_beta"]

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

def run():
    if not os.path.exists(PIF_DIR): os.makedirs(PIF_DIR)
    if not os.path.exists(DB_FILE): 
        with open(DB_FILE, 'w') as f: f.write("")

    with open(DB_FILE, 'r') as f:
        used_fps = {line.strip() for line in f if line.strip()}

    # Get current month and year (e.g., "2026-04")
    current_month_prefix = datetime.now().strftime("%Y-%m")
    print(f"🛰️ Scanning for Beta builds with Security Patch: {current_month_prefix}")
    
    api_url = f"https://api.github.com/repos/{SOURCE_REPO}/releases/latest"
    try:
        response = requests.get(api_url).json()
    except: return

    new_count = 0
    for asset in response.get('assets', []):
        if not asset['name'].endswith('.zip'): continue
        
        try:
            r = requests.get(asset['browser_download_url'])
            with zipfile.ZipFile(BytesIO(r.content)) as z:
                content_pool = ""
                for file_name in z.namelist():
                    if file_name.endswith('.prop') or 'build.prop' in file_name:
                        with z.open(file_name) as f:
                            content_pool += f.read().decode('utf-8', errors='ignore') + "\n"

                fp = extract_value(content_pool, SCHEMA["FINGERPRINT"])
                patch = extract_value(content_pool, SCHEMA["SECURITY_PATCH"])
                
                # Logic: Must be Beta AND match the current month's patch
                is_beta = any(word in fp.lower() or word in asset['name'].lower() for word in BETA_KEYWORDS)
                is_current = patch.startswith(current_month_prefix)

                if fp and is_beta and is_current and fp not in used_fps:
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
                        "VERSION:SECURITY_PATCH": patch,
                        "VERSION:API_LEVEL": sdk_val,
                        "VERSION:SDK_LEVEL": sdk_val
                    }

                    file_path = os.path.join(PIF_DIR, asset['name'].replace('.zip', '.json'))
                    with open(file_path, 'w') as out:
                        json.dump(pif_data, out, indent=2)
                    
                    with open(DB_FILE, 'a') as db:
                        db.write(fp + "\n")
                    
                    used_fps.add(fp)
                    print(f"✅ Found {current_month_prefix} Beta: {asset['name']}")
                    new_count += 1
        except Exception as e:
            print(f"Skipped {asset['name']}: {e}")

    print(f"🏁 Finished. Added {new_count} fingerprints from the current month.")

if __name__ == "__main__":
    run()
