const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const AdmZip = require('adm-zip');

const PIF_DIR = './pif_library';
const DB_FILE = './used_fingerprints.txt';
const TEMP_ZIPS = './temp_zips';

const PROPERTY_MAP = {
    PRODUCT: [/ro\.product\.system\.name=/m, /ro\.product\.name=/m],
    DEVICE: [/ro\.product\.system\.device=/m, /ro\.product\.device=/m],
    MANUFACTURER: [/ro\.product\.system\.manufacturer=/m, /ro\.product\.manufacturer=/m],
    BRAND: [/ro\.product\.system\.brand=/m, /ro\.product\.brand=/m],
    MODEL: [/ro\.product\.system\.model=/m, /ro\.product\.model=/m],
    FINGERPRINT: [/ro\.system\.build\.fingerprint=/m, /ro\.build\.fingerprint=/m],
    SECURITY_PATCH: [/ro\.build\.version\.security_patch=/m],
    ID: [/ro\.build\.id=/m],
    VERSION: [/ro\.build\.version\.release=/m]
};

function getProp(content, patterns) {
    for (const regex of patterns) {
        const match = content.split('\n').find(line => line.match(regex));
        if (match) return match.split('=')[1].trim();
    }
    return "";
}

async function run() {
    if (!fs.existsSync(PIF_DIR)) fs.mkdirSync(PIF_DIR);
    if (!fs.existsSync(TEMP_ZIPS)) fs.mkdirSync(TEMP_ZIPS);

    const used = fs.existsSync(DB_FILE) 
        ? fs.readFileSync(DB_FILE, 'utf8').split('\n').map(f => f.trim()).filter(Boolean) 
        : [];

    console.log("📦 Syncing with Pixel-Props...");
    try {
        execSync(`gh release download --repo Pixel-Props/build.prop --pattern "*.zip" --dest ${TEMP_ZIPS}`);
    } catch (e) { console.log("No new updates."); }

    const zips = fs.readdirSync(TEMP_ZIPS).filter(f => f.endsWith('.zip'));
    let count = 0;

    for (const file of zips) {
        try {
            const zip = new AdmZip(path.join(TEMP_ZIPS, file));
            let data = "";
            zip.getEntries().forEach(e => {
                if (e.entryName.endsWith('.prop') || e.entryName.includes('build.prop')) {
                    data += e.getData().toString('utf8') + "\n";
                }
            });

            const fp = getProp(data, PROPERTY_MAP.FINGERPRINT);
            if (fp && !used.includes(fp)) {
                const pif = {
                    PRODUCT: getProp(data, PROPERTY_MAP.PRODUCT),
                    DEVICE: getProp(data, PROPERTY_MAP.DEVICE),
                    MANUFACTURER: getProp(data, PROPERTY_MAP.MANUFACTURER),
                    BRAND: getProp(data, PROPERTY_MAP.BRAND),
                    MODEL: getProp(data, PROPERTY_MAP.MODEL),
                    FINGERPRINT: fp,
                    SECURITY_PATCH: getProp(data, PROPERTY_MAP.SECURITY_PATCH),
                    FIRST_API_LEVEL: "25",
                    ID: getProp(data, PROPERTY_MAP.ID),
                    VERSION: getProp(data, PROPERTY_MAP.VERSION)
                };
                fs.writeFileSync(path.join(PIF_DIR, file.replace('.zip', '.json')), JSON.stringify(pif, null, 2));
                fs.appendFileSync(DB_FILE, fp + "\n");
                count++;
            }
        } catch (err) { console.error(`Error: ${file}`, err.message); }
    }
    fs.rmSync(TEMP_ZIPS, { recursive: true, force: true });
}
run();

