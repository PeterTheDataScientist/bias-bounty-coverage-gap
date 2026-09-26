#!/usr/bin/env bash
# Build PROJ 9.5.1 with fused multiply-add and lay it over the installed pyproj 3.7.2 wheel, so that
# pipeline.py runs with the arithmetic the reference scores were built with (WRITEUP.md, section 9).
#
#   bash tools/build_proj_fma.sh
#   PYTHONPATH=proj_fma python pipeline.py --check
#
# Linux x86-64 on a CPU with FMA (Intel and AMD since about 2013). Needs cmake, a C++ compiler and
# sqlite3 (Debian/Ubuntu: apt install cmake g++ sqlite3 libsqlite3-dev). About 2 minutes on 2 cores.
# The control build, which matches the pyproj wheel bit for bit:
#   FLAGS="-O2 -mno-fma -ffp-contract=off" OUT=proj_nofma bash tools/build_proj_fma.sh
set -euo pipefail
FLAGS="${FLAGS:--O2 -mfma -ffp-contract=fast}"
OUT="${OUT:-proj_fma}"
PY="${PYTHON:-python}"
V=9.5.1
SHA=a8395f9696338ffd46b0feb603edbb730fad6746fba77753c77f7f997345e3d3
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

for c in curl tar sha256sum cmake sqlite3; do
  command -v "$c" >/dev/null || { echo "build_proj_fma.sh: '$c' not found (Debian/Ubuntu: apt install curl cmake g++ sqlite3 libsqlite3-dev)" >&2; exit 1; }
done
command -v c++ >/dev/null || command -v g++ >/dev/null || { echo "build_proj_fma.sh: no C++ compiler found (apt install g++)" >&2; exit 1; }
"$PY" -c 'import pyproj; assert pyproj.__version__ == "3.7.2" and pyproj.proj_version_str == "9.5.1", (pyproj.__version__, pyproj.proj_version_str)' \
  || { echo "build_proj_fma.sh: needs pyproj 3.7.2 (PROJ 9.5.1) in $PY: pip install -r requirements.txt" >&2; exit 1; }
echo "downloading PROJ $V"
curl -sSfL -o "$WORK/proj.tar.gz" "https://github.com/OSGeo/PROJ/releases/download/$V/proj-$V.tar.gz"
echo "$SHA  $WORK/proj.tar.gz" | sha256sum -c -
tar xzf "$WORK/proj.tar.gz" -C "$WORK"
echo "building with CFLAGS/CXXFLAGS: $FLAGS"
cmake -S "$WORK/proj-$V" -B "$WORK/build" -DCMAKE_BUILD_TYPE=None \
  -DCMAKE_C_FLAGS="$FLAGS" -DCMAKE_CXX_FLAGS="$FLAGS" \
  -DENABLE_TIFF=OFF -DENABLE_CURL=OFF -DBUILD_TESTING=OFF -DBUILD_APPS=OFF > "$WORK/cmake.log"
cmake --build "$WORK/build" -j"$(nproc)" > "$WORK/build.log"
LIB="$(ls "$WORK"/build/lib/libproj.so.25.9.5.1)"

SITE="$("$PY" -c 'import os, pyproj; print(os.path.dirname(os.path.dirname(pyproj.__file__)))')"
rm -rf "$OUT" && mkdir -p "$OUT"
cp -r "$SITE/pyproj" "$SITE/pyproj.libs" "$OUT/"
BUNDLED="$(ls "$OUT"/pyproj.libs/libproj-*.so.25.9.5.1)"
cp "$LIB" "$BUNDLED"
echo "PROJ $V ($FLAGS) is now under ./$OUT"
PYTHONPATH="$OUT" "$PY" "$(dirname "$0")/fingerprint.py"
