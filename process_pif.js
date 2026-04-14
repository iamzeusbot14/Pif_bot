const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const AdmZip = require('adm-zip');

const PIF_DIR = './pif_library';
const DB_FILE = './used_fingerprints.txt';
const TEMP_ZIPS = './temp_zips';

const SCHEMA = {
    PRODUCT: [/ro\.product\.name=/m, /ro\.product\.system\.name=/m],
    DEVICE: [/ro\.product\.device=/m, /ro\.product\.system\.device=/m],
    MANUFACTURER: [/ro\.product\.manufacturer=/m, /ro\.product\.system\.manufacturer=/m],
    BRAND: [/ro\.product\.brand=/m, /ro\.product\.system\.brand=/m],
    MODEL: [/ro\.product\.model=/m, /ro\.product\.system\.model=/m],
    FINGERPRINT: [/ro\.build\.fingerprint=/m, /ro\.system\.build\.fingerprint=/m, /ro\.vendor\.build\.fingerprint=/m],
    SECURITY_PATCH: [/ro\.build\.version\.security_patch=/m],
    ID: [/ro\.build\.id=/m],
    VERSION: [/ro\.build\.version\.release=/m]
};

function extract(data, patterns) {
    for (const regex of patterns) {
        const match = data.match(regex);
        if (match) {
            const line = data.substring(match.index).split('\n')[0];
            return line.split('=')[1].trim();
        }
    }
    return "";
}

async function run() {
    if (!fs.existsSync(PIF_DIR)) fs.mkdirSync(PIF_DIR);
    if (!fs.existsSync(TEMP_ZIPS)) fs.mkdirSync(TEMP_ZIPS);

    const used = fs.existsSync(DB_FILE) ? fs.readFileSync(DB_FILE, 'utf8') : "";

    console.log("🚀 Running Deep Scan for Google Certified Props...");
    try {
        execSync(`gh release download --repo Pixel-Props/build.prop --pattern "*.zip" --dest ${TEMP_ZIPS}`);
    } catch (e) { console.log("No new updates available."); }

    const zips = fs.readdirSync(TEMP_ZIPS).filter(f => f.endsWith('.zip'));
    
    for (const file of zips) {
        try {
            const zip = new AdmZip(path.join(TEMP_ZIPS, file));
            let blob = "";
            zip.getEntries().forEach(e => {
                if (e.entryName.endsWith('.prop') || e.entryName.includes('build.prop')) {
                    blob += e.getData().toString('utf8') + "\n";
                }
            });

            const fp = extract(blob, SCHEMA.FINGERPRINT);

            if (fp && !used.includes(fp)) {
                const pif = {
                    PRODUCT: extract(blob, SCHEMA.PRODUCT),
                    DEVICE: extract(blob, SCHEMA.DEVICE),
                    MANUFACTURER: extract(blob, SCHEMA.MANUFACTURER),
                    BRAND: extract(blob, SCHEMA.BRAND),
                    MODEL: extract(blob, SCHEMA.MODEL),
                    FINGERPRINT: fp,
                    SECURITY_PATCH: extract(blob, SCHEMA.SECURITY_PATCH),
                    FIRST_API_LEVEL: "25",
                    ID: extract(blob, SCHEMA.ID),
                    VERSION: extract(blob, SCHEMA.VERSION)
                };

                fs.writeFileSync(path.join(PIF_DIR, file.replace('.zip', '.json')), JSON.stringify(pif, null, 2));
                fs.appendFileSync(DB_FILE, fp + "\n");
                console.log(`✅ Extracted: ${file}`);
            }
        } catch (err) { console.log(`Skipped ${file}`); }
    }
    fs.rmSync(TEMP_ZIPS, { recursive: true, force: true });
}

run();
