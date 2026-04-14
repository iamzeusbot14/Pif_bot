#!/bin/bash

# Create directories
mkdir -p pif_library
mkdir -p temp_zips

# 1. Download latest props from Pixel-Props
# Using the GitHub CLI (built into GH Actions runners)
gh release download --repo Pixel-Props/build.prop --pattern "*.zip" --dest ./temp_zips

# 2. Ensure database exists
touch used_fingerprints.txt

# 3. Process each zip
for zip in ./temp_zips/*.zip; do
    filename=$(basename "$zip" .zip)
    
    # Extract system.prop to memory
    unzip -p "$zip" system.prop > temp.prop
    
    # Extract fingerprint to check against database
    FP=$(grep "ro.build.fingerprint=" temp.prop | cut -d'=' -f2)
    
    # Skip if we've already used this fingerprint
    if grep -qx "$FP" used_fingerprints.txt; then
        echo "⏭️ Skipping $filename: Fingerprint already in database."
        continue
    fi

    # Extract required fields for Play Integrity Fix JSON
    MODEL=$(grep "ro.product.model=" temp.prop | cut -d'=' -f2)
    BRAND=$(grep "ro.product.brand=" temp.prop | cut -d'=' -f2)
    DEVICE=$(grep "ro.product.device=" temp.prop | cut -d'=' -f2)
    RELEASE=$(grep "ro.build.version.release=" temp.prop | cut -d'=' -f2)
    ID=$(grep "ro.build.id=" temp.prop | cut -d'=' -f2)
    PATCH=$(grep "ro.build.version.security_patch=" temp.prop | cut -d'=' -f2)

    # 4. Generate the individual JSON file
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
    # Add to database to prevent repeat in future runs
    echo "$FP" >> used_fingerprints.txt
    echo "✅ Generated new JSON for $filename"
done

# Cleanup
rm -rf temp_zips temp.prop
