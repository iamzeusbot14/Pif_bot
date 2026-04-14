#!/bin/bash

mkdir -p pif_library
mkdir -p temp_zips

# 1. Download latest props from Pixel-Props
gh release download --repo Pixel-Props/build.prop --pattern "*.zip" --dest ./temp_zips

# 2. Load the used fingerprints list (database)
touch used_fingerprints.txt

for zip in ./temp_zips/*.zip; do
    filename=$(basename "$zip" .zip)
    
    # Extract system.prop content
    unzip -p "$zip" system.prop > temp.prop
    
    # Extract fingerprint to check against database
    FP=$(grep "ro.build.fingerprint=" temp.prop | cut -d'=' -f2)
    
    # 3. Database Check: Skip if already used
    if grep -q "$FP" used_fingerprints.txt; then
        echo "Skipping $filename (already used)."
        continue
    fi

    # Extract other variables
    MODEL=$(grep "ro.product.model=" temp.prop | cut -d'=' -f2)
    BRAND=$(grep "ro.product.brand=" temp.prop | cut -d'=' -f2)
    DEVICE=$(grep "ro.product.device=" temp.prop | cut -d'=' -f2)
    RELEASE=$(grep "ro.build.version.release=" temp.prop | cut -d'=' -f2)
    ID=$(grep "ro.build.id=" temp.prop | cut -d'=' -f2)
    PATCH=$(grep "ro.build.version.security_patch=" temp.prop | cut -d'=' -f2)

    # 4. Generate individual JSON
    cat <<EOF > "pif_library/${filename}.json"
{
  "PRODUCT": "$DEVICE",
  "DEVICE": "$DEVICE",
  "MANUFACTURER": "$BRAND",
  "BRAND": "$BRAND",
  "MODEL": "$MODEL",
  "FINGERPRINT": "$FP",
  "SECURITY_PATCH": "$PATCH",
  "FIRST_API_LEVEL": "25",
  "ID": "$ID",
  "VERSION": "$RELEASE"
}
EOF
    # Mark as used
    echo "$FP" >> used_fingerprints.txt
    echo "Generated unique PIF for $filename"
done

