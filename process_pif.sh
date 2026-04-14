#!/bin/bash

# Setup directories
mkdir -p pif_library
mkdir -p temp_zips

# 1. Download latest releases from Pixel-Props
gh release download --repo Pixel-Props/build.prop --pattern "*.zip" --dest ./temp_zips

# 2. Database check to prevent duplicates
touch used_fingerprints.txt

for zip in ./temp_zips/*.zip; do
    filename=$(basename "$zip" .zip)
    
    # Extract ALL files to find the correct props
    unzip -o "$zip" -d "extracted_$filename"
    find "extracted_$filename" -name "*.prop" -o -name "build.prop" | xargs cat > full_data.tmp

    # Extract the Fingerprint
    FP=$(grep "ro.build.fingerprint=" full_data.tmp | head -n 1 | cut -d'=' -f2)
    
    # Skip if empty or already exists in our database
    if [ -z "$FP" ] || grep -qx "$FP" used_fingerprints.txt; then
        rm -rf "extracted_$filename"
        continue
    fi

    # Extract variables for JSON
    MODEL=$(grep "ro.product.model=" full_data.tmp | head -n 1 | cut -d'=' -f2)
    BRAND=$(grep "ro.product.brand=" full_data.tmp | head -n 1 | cut -d'=' -f2)
    DEVICE=$(grep "ro.product.device=" full_data.tmp | head -n 1 | cut -d'=' -f2)
    RELEASE=$(grep "ro.build.version.release=" full_data.tmp | head -n 1 | cut -d'=' -f2)
    ID=$(grep "ro.build.id=" full_data.tmp | head -n 1 | cut -d'=' -f2)
    PATCH=$(grep "ro.build.version.security_patch=" full_data.tmp | head -n 1 | cut -d'=' -f2)
    MANUFACTURER=$(grep "ro.product.manufacturer=" full_data.tmp | head -n 1 | cut -d'=' -f2)

    # 3. Create the individual JSON
    cat <<EOF > "pif_library/${filename}.json"
{
  "PRODUCT": "$DEVICE",
  "DEVICE": "$DEVICE",
  "MANUFACTURER": "${MANUFACTURER:-$BRAND}",
  "BRAND": "$BRAND",
  "MODEL": "$MODEL",
  "FINGERPRINT": "$FP",
  "SECURITY_PATCH": "$PATCH",
  "FIRST_API_LEVEL": "25",
  "ID": "$ID",
  "VERSION": "$RELEASE"
}
EOF
    # Mark as used in our tracker
    echo "$FP" >> used_fingerprints.txt
    rm -rf "extracted_$filename"
done

rm -f full_data.tmp
