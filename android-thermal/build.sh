#!/usr/bin/env bash
# Build the pyontrust Thermal APK without Gradle: aapt2 → javac → d8 → zipalign → apksigner.
#
#   ./build.sh                 # → build/pyontrust-thermal.apk
#   ./build.sh install         # + install on every authorised adb device and
#                              #   forward the gateway port (adb reverse tcp:5210)
#
# Needs: Android SDK (ANDROID_HOME, default ~/Android) with platforms;android-34
# and build-tools;34.0.0, and a JDK 17 (JAVA_HOME, default ~/.local/jdk17).
set -euo pipefail
cd "$(dirname "$0")"

SDK="${ANDROID_HOME:-$HOME/Android}"
BT="$SDK/build-tools/34.0.0"
JAR="$SDK/platforms/android-34/android.jar"
export JAVA_HOME="${JAVA_HOME:-$HOME/.local/jdk17}"
export PATH="$JAVA_HOME/bin:$PATH"
KEYSTORE="${PYONTRUST_CAM_KEYSTORE:-$HOME/.android/pyontrust-camera.jks}"   # same key as the camera app
OUT=build
VERSION="$(tr -dc 0-9 < VERSION)"
GATEWAY_PORT="${PYONTRUST_GATEWAY_PORT:-5210}"

for f in "$BT/aapt2" "$BT/d8" "$BT/zipalign" "$BT/apksigner" "$JAR"; do
  [[ -e "$f" ]] || { echo "missing $f — install platforms;android-34 and build-tools;34.0.0" >&2; exit 1; }
done

rm -rf "$OUT"; mkdir -p "$OUT/classes" "$OUT/dex"

# 1. resources + manifest → base APK
"$BT/aapt2" compile --dir res -o "$OUT/res.zip"
"$BT/aapt2" link -I "$JAR" --manifest AndroidManifest.xml -o "$OUT/base.apk" "$OUT/res.zip" \
  --min-sdk-version 21 --target-sdk-version 34 --version-code "$VERSION" --version-name "1.$VERSION"

# 2. Java → classes (Java 8 bytecode, Android API 34 as the boot classpath)
javac -source 8 -target 8 -bootclasspath "$JAR:$BT/core-lambda-stubs.jar" -Xlint:-options -encoding UTF-8 \
  -d "$OUT/classes" $(find src -name '*.java')

# 3. classes → dex
"$BT/d8" --release --min-api 21 --lib "$JAR" --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')

# 4. add dex, align, sign
cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT/dex" && zip -q -j ../unsigned.apk classes.dex)
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
if [[ ! -f "$KEYSTORE" ]]; then
  mkdir -p "$(dirname "$KEYSTORE")"
  keytool -genkeypair -keystore "$KEYSTORE" -storepass android -keypass android -alias pyontrust \
    -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=pyontrust camera" >/dev/null
fi
"$BT/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --out "$OUT/pyontrust-thermal.apk" "$OUT/aligned.apk"
mkdir -p dist
cp "$OUT/pyontrust-thermal.apk" "dist/pyontrust-thermal-1.$VERSION.apk"   # stand-alone copy to sideload on any phone
echo "built $OUT/pyontrust-thermal.apk ($(du -h "$OUT/pyontrust-thermal.apk" | cut -f1)) → dist/pyontrust-thermal-1.$VERSION.apk"

if [[ "${1:-}" == "install" ]]; then
  for serial in $(adb devices | awk 'NR>1 && $2=="device" {print $1}'); do
    echo "installing on $serial"
    adb -s "$serial" install -r -g "$OUT/pyontrust-thermal.apk"
    adb -s "$serial" reverse "tcp:$GATEWAY_PORT" "tcp:$GATEWAY_PORT" >/dev/null \
      && echo "  gateway reachable on the phone at http://127.0.0.1:$GATEWAY_PORT"
  done
fi
