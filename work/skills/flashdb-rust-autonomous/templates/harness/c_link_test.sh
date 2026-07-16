#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[c_link_test] cargo build --release"
cargo build --release

LIB="$ROOT/target/release/libflashdb_rust.a"
if [ ! -s "$LIB" ]; then
  echo "[c_link_test] FAIL: missing or empty static library: $LIB" >&2
  exit 1
fi

C_TEST_DIR="$ROOT/../FlashDB/tests"
if [ ! -d "$C_TEST_DIR" ]; then
  echo "[c_link_test] FAIL: missing C test directory: $C_TEST_DIR" >&2
  exit 1
fi

CC_BIN="${CC:-gcc}"
link_libs=(-lpthread -ldl -lm)

(
  cd "$C_TEST_DIR"
  rm -f kvdb_main.o tsdb_main.o kvdb_test tsdb_test
  rm -rf fdb_kvdb1/ fdb_tsdb1/ storage_* storage_tsdb

  echo "[c_link_test] compile kvdb_main.c"
  "$CC_BIN" -c kvdb_main.c -I. -I../inc -I../src -o kvdb_main.o

  echo "[c_link_test] compile tsdb_main.c"
  "$CC_BIN" -c tsdb_main.c -I. -I../inc -I../src -o tsdb_main.o

  echo "[c_link_test] link kvdb_test against libflashdb_rust.a"
  "$CC_BIN" -o kvdb_test kvdb_main.o -L../../flashDB_rust/target/release -lflashdb_rust "${link_libs[@]}"

  echo "[c_link_test] link tsdb_test against libflashdb_rust.a"
  "$CC_BIN" -o tsdb_test tsdb_main.o -L../../flashDB_rust/target/release -lflashdb_rust "${link_libs[@]}"

  echo "[c_link_test] run kvdb_test"
  rm -rf fdb_kvdb1/ fdb_tsdb1/ storage_* storage_tsdb
  ./kvdb_test

  echo "[c_link_test] run tsdb_test"
  rm -rf fdb_kvdb1/ fdb_tsdb1/ storage_* storage_tsdb
  ./tsdb_test
)

echo "[c_link_test] PASS"
