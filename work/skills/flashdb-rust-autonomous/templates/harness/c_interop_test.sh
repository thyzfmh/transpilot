#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT/../FlashDB"
BUILD="$ROOT/reports/interop-build"
DRIVER="$ROOT/harness/interop/interop_driver.c"
CC_BIN="${CC:-cc}"

cd "$ROOT"
cargo build --release
test -s target/release/libflashdb_rust.a

rm -rf "$BUILD"
mkdir -p "$BUILD"

common_flags=(-O0 -g -Wall -Wextra -I"$SOURCE/tests" -I"$SOURCE/inc" -I"$SOURCE/src")
link_libs=(-lpthread -ldl -lm)

"$CC_BIN" "${common_flags[@]}" -c "$DRIVER" -o "$BUILD/interop_driver.o"
"$CC_BIN" "${common_flags[@]}" -c "$SOURCE/src/fdb.c" -o "$BUILD/fdb.o"
"$CC_BIN" "${common_flags[@]}" -c "$SOURCE/src/fdb_file.c" -o "$BUILD/fdb_file.o"
"$CC_BIN" "${common_flags[@]}" -c "$SOURCE/src/fdb_kvdb.c" -o "$BUILD/fdb_kvdb.o"
"$CC_BIN" "${common_flags[@]}" -c "$SOURCE/src/fdb_tsdb.c" -o "$BUILD/fdb_tsdb.o"
"$CC_BIN" "${common_flags[@]}" -c "$SOURCE/src/fdb_utils.c" -o "$BUILD/fdb_utils.o"

"$CC_BIN" -o "$BUILD/interop_c" \
  "$BUILD/interop_driver.o" "$BUILD/fdb.o" "$BUILD/fdb_file.o" \
  "$BUILD/fdb_kvdb.o" "$BUILD/fdb_tsdb.o" "$BUILD/fdb_utils.o" "${link_libs[@]}"
"$CC_BIN" -o "$BUILD/interop_rust" "$BUILD/interop_driver.o" \
  -L"$ROOT/target/release" -lflashdb_rust "${link_libs[@]}"

"$BUILD/interop_c" kv-check-uninitialized
"$BUILD/interop_rust" kv-check-uninitialized

"$BUILD/interop_c" kv-produce "$BUILD/kv-c"
"$BUILD/interop_rust" kv-verify "$BUILD/kv-c" | tee "$BUILD/kv-c-to-rust.log"
grep -F "mode: next generation" "$BUILD/kv-c-to-rust.log" >/dev/null

"$BUILD/interop_rust" kv-produce "$BUILD/kv-rust" | tee "$BUILD/kv-rust-produce.log"
grep -F "mode: next generation" "$BUILD/kv-rust-produce.log" >/dev/null
"$BUILD/interop_c" kv-verify "$BUILD/kv-rust"
diff -r "$BUILD/kv-c" "$BUILD/kv-rust"

"$BUILD/interop_c" ts-produce "$BUILD/ts-c"
"$BUILD/interop_rust" ts-verify "$BUILD/ts-c"
"$BUILD/interop_rust" ts-produce "$BUILD/ts-rust"
"$BUILD/interop_c" ts-verify "$BUILD/ts-rust"
diff -r "$BUILD/ts-c" "$BUILD/ts-rust"

echo "C_INTEROP_TEST_PASS"
