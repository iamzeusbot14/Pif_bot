import os
import re
import json
import zipfile
import requests
from io import BytesIO

PIF_DIR = './pif_library'
DB_FILE = './used_fingerprints.txt'
SOURCE_REPO = "Pixel-Props/build.prop"

# Target Beta and Development builds specifically
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
    
    used_fps = set()
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            used_fps = {line.strip() for line in f if line.strip()}

    print("🛰️ Scanning for Certified Beta Properties...")
    api_url = f"https://api.github.com/repos/{SOURCE_REPO}/releases/latest"
    try:
        response = requests.get(api_url).json()
    except Exception as e:
        print(f"Connection failed: {e}")
        return

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
                
                # Filter logic: Must contain beta keywords
                is_beta = any(word in fp.lower() or word in asset['name'].lower() for word in BETA_KEYWORDS)

                if fp and is_beta and fp not in used_fps:
                    api = extract_value(content_pool, SCHEMA["API_LEVEL"])
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
                        "VERSION:API_LEVEL": int(api) if api.isdigit() else 25,
                        "VERSION:SDK_LEVEL": int(api) if api.isdigit() else 25
                    }

                    file_path = os.path.join(PIF_DIR, asset['name'].replace('.zip', '.json'))
                    with open(file_path, 'w') as out:
                        json.dump(pif_data, out, indent=2)
                    
                    with open(DB_FILE, 'a') as db:
                        db.write(fp + "\n")
                    print(f"🔥 Beta PIF Cached: {asset['name']}")
        except Exception as e:
            print(f"Skipped {asset['name']}: {e}")

if __name__ == "__main__":
    run()
