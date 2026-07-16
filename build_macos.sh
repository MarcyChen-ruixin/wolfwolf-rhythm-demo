#!/usr/bin/env bash
# Build Werewolf Rhythm Demo macOS .app (Apple Silicon or Intel — native to host).
# Run only on macOS. Does not upload or notarize.

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: build_macos.sh must run on macOS (Darwin)." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VERSION="0.1.0"
APP_NAME="Werewolf Rhythm Demo.app"
APP_PATH="dist/${APP_NAME}"
EXECUTABLE="${APP_PATH}/Contents/MacOS/WerewolfRhythmDemo"
SPEC="packaging/WerewolfRhythmDemo-macOS.spec"
VENV_DIR="${ROOT}/.venv-macos"

HOST_ARCH="$(uname -m)"
echo "==> Host CPU architecture: ${HOST_ARCH}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
echo "==> Python executable: ${PYTHON_BIN}"
"${PYTHON_BIN}" -c "import platform,sys; print(f'Python {sys.version.split()[0]} arch={platform.machine()}')"

if [[ "${HOST_ARCH}" == "arm64" ]]; then
  ARCH_LABEL="AppleSilicon"
  EXPECT_ARCH="arm64"
elif [[ "${HOST_ARCH}" == "x86_64" ]]; then
  ARCH_LABEL="Intel"
  EXPECT_ARCH="x86_64"
else
  echo "ERROR: unsupported architecture ${HOST_ARCH}" >&2
  exit 1
fi

ZIP_NAME="WerewolfRhythm-Demo-macOS-${ARCH_LABEL}-v${VERSION}.zip"
SHA_NAME="WerewolfRhythm-Demo-macOS-${ARCH_LABEL}-v${VERSION}.sha256"
OUT_DIR="${ROOT}/dist/release"
mkdir -p "${OUT_DIR}"

echo "==> Creating / refreshing virtual environment: ${VENV_DIR}"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements-macos.txt

echo "==> Cleaning stale macOS build outputs"
rm -rf build/WerewolfRhythmDemo dist/WerewolfRhythmDemo "${APP_PATH}"
rm -f "${OUT_DIR}/${ZIP_NAME}" "${OUT_DIR}/${SHA_NAME}"

# Optional icon: build .icns from authorized public PNG if present.
ICON_SRC=""
for candidate in \
  "assets/art/icon.png" \
  "packaging/icon.png" \
  "assets/art/werewolf_enemy_1.png"
do
  # Only accept a dedicated icon.png — do not repurpose enemy art.
  if [[ "${candidate}" == *"/icon.png" && -f "${candidate}" ]]; then
    ICON_SRC="${candidate}"
    break
  fi
done

if [[ -n "${ICON_SRC}" ]]; then
  echo "==> Building packaging/WerewolfRhythmDemo.icns from ${ICON_SRC}"
  ICONSET="${ROOT}/packaging/WerewolfRhythmDemo.iconset"
  rm -rf "${ICONSET}"
  mkdir -p "${ICONSET}"
  sips -z 16 16     "${ICON_SRC}" --out "${ICONSET}/icon_16x16.png" >/dev/null
  sips -z 32 32     "${ICON_SRC}" --out "${ICONSET}/diana.andreeva@example.net" >/dev/null
  sips -z 32 32     "${ICON_SRC}" --out "${ICONSET}/icon_32x32.png" >/dev/null
  sips -z 64 64     "${ICON_SRC}" --out "${ICONSET}/ivan.p@example.net" >/dev/null
  sips -z 128 128   "${ICON_SRC}" --out "${ICONSET}/icon_128x128.png" >/dev/null
  sips -z 256 256   "${ICON_SRC}" --out "${ICONSET}/wendy.h@example.net" >/dev/null
  sips -z 256 256   "${ICON_SRC}" --out "${ICONSET}/icon_256x256.png" >/dev/null
  sips -z 512 512   "${ICON_SRC}" --out "${ICONSET}/wendy.h@example.net" >/dev/null
  sips -z 512 512   "${ICON_SRC}" --out "${ICONSET}/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "${ICON_SRC}" --out "${ICONSET}/walt.e@example.net" >/dev/null
  iconutil -c icns "${ICONSET}" -o "${ROOT}/packaging/WerewolfRhythmDemo.icns"
  rm -rf "${ICONSET}"
else
  echo "==> No authorized assets/art/icon.png found — using default macOS app icon"
  rm -f "${ROOT}/packaging/WerewolfRhythmDemo.icns"
fi

echo "==> PyInstaller macOS .app build"
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-dummy}"
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-dummy}"
python -m PyInstaller --noconfirm --clean "${SPEC}"

if [[ ! -d "${APP_PATH}" ]]; then
  echo "ERROR: missing ${APP_PATH}" >&2
  exit 1
fi
if [[ ! -x "${EXECUTABLE}" ]]; then
  echo "ERROR: missing executable ${EXECUTABLE}" >&2
  exit 1
fi

echo "==> Verifying required assets inside bundle"
REQUIRED_ASSETS=(
  "assets/art/werewolf_background.png"
  "assets/art/werewolf_enemy_1.png"
  "assets/art/werewolf_enemy_2.png"
  "assets/art/werewolf_enemy_3.png"
  "assets/art/werewolf_enemy_hold.png"
  "assets/art/werewolf_enemy_miss.png"
  "assets/art/hold_sequence/werewolf_hold_01.png"
  "assets/audio/monkeys-spinning-monkeys.mp3"
  "assets/audio/fluffing-a-duck.mp3"
  "assets/audio/sneaky-snitch.mp3"
)
ASSET_ROOT=""
for candidate in \
  "${APP_PATH}/Contents/Resources" \
  "${APP_PATH}/Contents/Frameworks" \
  "${APP_PATH}/Contents/MacOS" \
  "${APP_PATH}/Contents/Frameworks/_internal" \
  "${APP_PATH}/Contents/Resources/_internal"
do
  if [[ -d "${candidate}/assets" ]]; then
    ASSET_ROOT="${candidate}"
    break
  fi
done
if [[ -z "${ASSET_ROOT}" ]]; then
  # Search once under the bundle
  ASSET_ROOT="$(find "${APP_PATH}" -type d -name assets | head -n 1 | xargs dirname 2>/dev/null || true)"
fi
if [[ -z "${ASSET_ROOT}" || ! -d "${ASSET_ROOT}/assets" ]]; then
  echo "ERROR: assets folder not found inside ${APP_PATH}" >&2
  find "${APP_PATH}" -maxdepth 4 -type d -print >&2 || true
  exit 1
fi
for rel in "${REQUIRED_ASSETS[@]}"; do
  if [[ ! -f "${ASSET_ROOT}/${rel}" ]]; then
    echo "ERROR: missing bundled asset ${rel} under ${ASSET_ROOT}" >&2
    exit 1
  fi
done
echo "    assets ok under ${ASSET_ROOT}"

echo "==> Ad-hoc code signing"
codesign --force --deep --sign - "${APP_PATH}"
codesign --verify --deep --strict --verbose=2 "${APP_PATH}"

echo "==> Architecture validation"
FILE_OUT="$(file "${EXECUTABLE}")"
echo "    file: ${FILE_OUT}"
LIPO_OUT="$(lipo -info "${EXECUTABLE}" 2>/dev/null || true)"
echo "    lipo: ${LIPO_OUT}"
if ! echo "${FILE_OUT} ${LIPO_OUT}" | grep -q "${EXPECT_ARCH}"; then
  echo "ERROR: executable is not ${EXPECT_ARCH}" >&2
  exit 1
fi
# Reject accidental universal2 / wrong-arch packages for this workflow.
if echo "${LIPO_OUT}" | grep -qi "Architectures in the fat file"; then
  echo "ERROR: unexpected fat/universal binary; native single-arch build required" >&2
  exit 1
fi

echo "==> Packaged self-test"
export SDL_VIDEODRIVER=dummy
export SDL_AUDIODRIVER=dummy
"${EXECUTABLE}" --self-test

echo "==> Creating ZIP with ditto"
ditto -c -k --sequesterRsrc --keepParent \
  "${APP_PATH}" \
  "${OUT_DIR}/${ZIP_NAME}"

echo "==> SHA-256 checksum"
(
  cd "${OUT_DIR}"
  shasum -a 256 "${ZIP_NAME}" | tee "${SHA_NAME}"
)

echo ""
echo "Build OK (${ARCH_LABEL} / ${EXPECT_ARCH})"
echo "  App:  ${APP_PATH}"
echo "  ZIP:  ${OUT_DIR}/${ZIP_NAME}"
echo "  SHA:  ${OUT_DIR}/${SHA_NAME}"
echo "NOTE: Ad-hoc signed and not notarized."
