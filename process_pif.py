import os
import re
import json
import zipfile
import requests
from io import BytesIO

PIF_DIR = './pif_library'
DB_FILE = './used_fingerprints.txt'
SOURCE_REPO = "Pixel-Props/build.prop"

# Certification schema with prioritized regex patterns
SCHEMA = {
    "PRODUCT": [r"ro\.product\.name=(.*)", r"ro\.product\.system\.name=(.*)"],
    "DEVICE": [r"ro\.product\.device=(.*)", r"ro\.product\.system\.device=(.*)"],
    "MANUFACTURER": [r"ro\.product\.manufacturer=(.*)", r"ro\.product\.system\.manufacturer=(.*)"],
    "BRAND": [r"ro\.product\.brand=(.*)", r"ro\.product\.system\.brand=(.*)"],
    "MODEL": [r"ro\.product\.model=(.*)", r"ro\.product\.system\.model=(.*)"],
    "FINGERPRINT": [r"ro\.build\.fingerprint=(.*)", r"ro\.system\.build\.fingerprint=(.*)"],
    "SECURITY_PATCH": [r"ro\.build\.version\.security_patch=(.*)"],
    "ID": [r"ro\.build\.id=(.*)"],
    "VERSION": [r"ro\.build\.version\.release=(.*)"]
}

def extract_value(data, patterns):
    for pattern in patterns:
        match = re.search(pattern, data)
        if match:
            return match.group(1).strip()
    return ""

def run():
    if not os.path.exists(PIF_DIR): os.makedirs(PIF_DIR)
    
    # Load database
    used_fps = set()
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            used_fps = {line.strip() for line in f if line.strip()}

    print("🚀 Fetching latest releases from Pixel-Props...")
    api_url = f"https://api.github.com/repos/{SOURCE_REPO}/releases/latest"
    response = requests.get(api_url).json()

    new_count = 0
    for asset in response.get('assets', []):
        if not asset['name'].endswith('.zip'): continue
        
        print(f"📦 Processing: {asset['name']}")
        r = requests.get(asset['browser_download_url'])
        with zipfile.ZipFile(BytesIO(r.content)) as z:
            content_pool = ""
            for file_name in z.namelist():
                if file_name.endswith('.prop') or 'build.prop' in file_name:
                    with z.open(file_name) as f:
                        content_pool += f.read().decode('utf-8', errors='ignore') + "\n"

            fp = extract_value(content_pool, SCHEMA["FINGERPRINT"])

            if fp and fp not in used_fps:
                pif_data = {
                    "PRODUCT": extract_value(content_pool, SCHEMA["PRODUCT"]),
                    "DEVICE": extract_value(content_pool, SCHEMA["DEVICE"]),
                    "MANUFACTURER": extract_value(content_pool, SCHEMA["MANUFACTURER"]),
                    "BRAND": extract_value(content_pool, SCHEMA["BRAND"]),
                    "MODEL": extract_value(content_pool, SCHEMA["MODEL"]),
                    "FINGERPRINT": fp,
                    "SECURITY_PATCH": extract_value(content_pool, SCHEMA["SECURITY_PATCH"]),
                    "FIRST_API_LEVEL": "25", # The magic number for bypass
                    "ID": extract_value(content_pool, SCHEMA["ID"]),
                    "VERSION": extract_value(content_pool, SCHEMA["VERSION"])
                }

                file_path = os.path.join(PIF_DIR, asset['name'].replace('.zip', '.json'))
                with open(file_path, 'w') as out:
                    json.dump(pif_data, out, indent=2)
                
                with open(DB_FILE, 'a') as db:
                    db.write(fp + "\n")
                
                print(f"✅ Generated: {asset['name']}")
                new_count += 1

    print(f"\n🏁 Finished. {new_count} new profiles added.")

if __name__ == "__main__":
    run()
