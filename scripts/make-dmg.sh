#!/bin/sh
# Make the macOS disk image from dist/Mathessible.app (PyInstaller's) with create-dmg (Homebrew): the
# application and a link to /Applications. Usage: scripts/make-dmg.sh <output.dmg>
#
# Signing and notarisation are optional, so that a build without Apple credentials still gives a DMG:
# - MATHESSIBLE_CODESIGN_IDENTITY (a Developer ID Application in the keychain) signs the image; the
#   application itself is signed by the PyInstaller spec, with the same variable.
# - APPLE_API_KEY_PATH, APPLE_API_KEY_ID and APPLE_API_ISSUER (an App Store Connect API key) also
#   notarise the image and staple the ticket to it, so it opens without a network connection.
set -eu

output=${1:?"usage: scripts/make-dmg.sh <output.dmg>"}
root=$(cd "$(dirname "$0")/.." && pwd)
app="$root/dist/Mathessible.app"
[ -d "$app" ] || { echo "No $app: run PyInstaller first." >&2; exit 1; }

identity=${MATHESSIBLE_CODESIGN_IDENTITY:-}
if [ -n "$identity" ]; then
    codesign --verify --deep --strict --verbose=2 "$app"
fi

command -v create-dmg > /dev/null || { echo "create-dmg is missing: brew install create-dmg" >&2; exit 1; }
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
cp -R "$app" "$staging/"
rm -f "$output"
# The Finder window: the application on the left, the link to /Applications on the right.
create-dmg \
    --volname Mathessible \
    --volicon "$root/packaging/Mathessible.icns" \
    --window-size 540 320 \
    --icon-size 112 \
    --icon Mathessible.app 140 150 \
    --hide-extension Mathessible.app \
    --app-drop-link 400 150 \
    --hdiutil-quiet \
    "$output" "$staging"

if [ -n "$identity" ]; then
    codesign --sign "$identity" --timestamp "$output"
    if [ -n "${APPLE_API_KEY_PATH:-}" ]; then
        xcrun notarytool submit "$output" --wait \
            --key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER"
        xcrun stapler staple "$output"
        spctl --assess --type open --context context:primary-signature --verbose=2 "$output"
    else
        echo "Signed but not notarised: no APPLE_API_KEY_PATH." >&2
    fi
else
    echo "Not signed: no MATHESSIBLE_CODESIGN_IDENTITY." >&2
fi
