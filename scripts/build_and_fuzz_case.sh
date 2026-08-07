#!/usr/bin/env bash
set -euo pipefail

case_dir="${1:?case artifact directory required}"
afl_out="${2:?AFL output directory required}"
timeout_ms="${3:-1000}"

mkdir -p "$case_dir/build" "$case_dir/seeds" "$afl_out"

if [ ! -f "$case_dir/seeds/empty" ]; then
  : > "$case_dir/seeds/empty"
fi

protoc --cpp_out="$case_dir/build" "$case_dir/input.proto"

clang \
  -std=c11 \
  -fsanitize=address,undefined \
  -I"$case_dir" \
  -c "$case_dir/c_adapter.c" \
  -o "$case_dir/build/c_adapter.o"

rustc \
  "$case_dir/rust_adapter.rs" \
  --crate-type staticlib \
  -C panic=abort \
  -o "$case_dir/build/libguardian_rust.a"

clang++ \
  -std=c++17 \
  -fsanitize=address,undefined \
  -I"$case_dir" \
  -I"$case_dir/build" \
  "$case_dir/differential_harness.cc" \
  "$case_dir/build/input.pb.cc" \
  "$case_dir/build/c_adapter.o" \
  "$case_dir/build/libguardian_rust.a" \
  -lprotobuf-mutator-libfuzzer \
  -lprotobuf \
  -lpthread \
  -ldl \
  -lm \
  -o "$case_dir/build/differential_harness"

AFL_SKIP_CPUFREQ=1 afl-fuzz \
  -i "$case_dir/seeds" \
  -o "$afl_out" \
  -V "$timeout_ms" \
  -- "$case_dir/build/differential_harness"
