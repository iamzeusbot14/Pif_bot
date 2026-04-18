import os, re, json, zipfile, requests, concurrent.futures
from io import BytesIO
from datetime import datetime

# --- ULTIMATE 2026 AUDIT CONFIG ---
BASE_PIF_DIR = './pif_library'
DB_FILE = './used_fingerprints.txt'
# Target April 2026 Security Patches & Android 17 (Baklava) Beta 4
PATCH_LEVELS = ["2026-04-01", "2026-04-05"]
BUILD_PREFIXES = ["BP4A", "CP21", "CP1A"]

SOURCES = [
    {"repo": "Pixel-Props/build.prop", "type": "zip"},
    {"repo": "daboynb/autojson", "type": "raw"},      # Critical for Android 17 leaks
    {"repo": "farman13/PIF", "type": "json"},         # Best for Indian region/early leaks
    {"repo": "osm0sis/PlayIntegrityFork", "type": "raw"},
    {"repo": "MeowDump/Integrity-Box", "type": "json"},
    {"repo": "BasGame1/Pixelify-Next", "type": "raw"} # Updated for Pixel 10 UI support
]

def parse_pif_data(content, source_name):
    is_json = content.strip().startswith('{')
    try:
        if is_json:
            j = json.loads(content)
            fp = j.get("FINGERPRINT") or j.get("ro.build.fingerprint")
            if not fp: return None
            pif = {
                "BRAND": j.get("BRAND") or "google",
                "DEVICE": j.get("DEVICE") or "unknown",
                "FINGERPRINT": fp,
                "MODEL": j.get("MODEL") or "Pixel",
                "ID": j.get("ID") or j.get("ro.build.id", "unknown"),
                "VERSION:SECURITY_PATCH": j.get("VERSION:SECURITY_PATCH") or re.search(r':(\d{4}-\d{2}-\d{2}):', fp).group(1),
                "VERSION:API_LEVEL": int(j.get("SDK_INT") or j.get("VERSION:API_LEVEL") or 32)
            }
        else:
            # Deep Regex for build.prop
            fp_match = re.search(r"ro\.build\.fingerprint=(.*)", content)
            if not fp_match: return None
            fp = fp_match.group(1).strip()
            pif = {
                "FINGERPRINT": fp,
                "DEVICE": re.search(r"ro\.product\.device=(.*)", content).group(1).strip(),
                "ID": re.search(r"ro\.build\.id=(.*)", content).group(1).strip(),
                "VERSION:SECURITY_PATCH": re.search(r':(\d{4}-\d{2}-\d{2}):', fp).group(1),
                "VERSION:API_LEVEL": 32
            }
        
        # ULTIMATE FILTER: Keep only 2026 April builds or A17 Beta
        is_ultimate = any(p in pif["VERSION:SECURITY_PATCH"] for p in PATCH_LEVELS) or \
                      any(b in pif["ID"] for b in BUILD_PREFIXES)
        
        if is_ultimate:
            category = "ultimate" if "beta" not in fp.lower() else "beta_17"
            return (fp, category, f"{pif['DEVICE']}_{pif['ID']}.json".replace("/", "_"), pif)
        return None
    except: return None

def process_source(s):
    found = []
    try:
        # Check GitHub Tree for 'Invisible' branch commits (The ultimate leak source)
        branch = requests.get(f"https://api.github.com/repos/{s['repo']}").json().get('default_branch', 'main')
        tree = requests.get(f"https://api.github.com/repos/{s['repo']}/git/trees/{branch}?recursive=1").json()
        for item in tree.get('tree', []):
            if item['path'].endswith(('.json', '.prop')):
                url = f"https://raw.githubusercontent.com/{s['repo']}/{branch}/{item['path']}"
                res = parse_pif_data(requests.get(url).text, item['path'])
                if res: found.append(res)
    except: pass
    return found

def run():
    for c in ["ultimate", "beta_17"]: os.makedirs(os.path.join(BASE_PIF_DIR, c), exist_ok=True)
    with open(DB_FILE, 'r') as f: used = {l.strip() for l in f if l.strip()}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as exe:
        results = [p for sub in list(exe.map(process_source, SOURCES)) for p in sub]

    new_count = 0
    with open(DB_FILE, 'a') as db:
        for fp, cat, fname, data in results:
            if fp not in used:
                with open(os.path.join(BASE_PIF_DIR, cat, fname), 'w') as f:
                    json.dump(data, f, indent=2)
                db.write(fp + "\n")
                used.add(fp)
                new_count += 1
                print(f"💎 [ULTIMATE] Secured: {fname}")
    print(f"🏁 Audit Complete. {new_count} new fingerprints added.")

if __name__ == "__main__": run()
