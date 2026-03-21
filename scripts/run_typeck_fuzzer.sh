#!/bin/bash
# Fuzz Luau's new type solver (V2) with grammar-generated programs.
# Usage: ./scripts/run_typeck_fuzzer.sh <luau_version> [num_seeds] [max_time]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

VERSION="${1:?Usage: $0 <luau_version> [num_seeds] [max_time]}"
NUM_SEEDS="${2:-200}"
MAX_TIME="${3:-300}"

IMAGE_TAG="cs295-luau-$VERSION-typeck"

echo "=== Luau Type Checker Fuzzer ==="
echo "Version:  $VERSION"
echo "Seeds:    $NUM_SEEDS"
echo "Time:     ${MAX_TIME}s"
echo ""

# Build Docker image with Luau at the specified version
echo "=== Building Luau $VERSION ==="
docker build -q -t "$IMAGE_TAG" -f - "$PROJECT_DIR" << DOCKERFILE
FROM ubuntu:jammy
RUN apt-get update && apt-get install -y llvm-14 clang-14 lld-14 cmake make git python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN update-alternatives --install /usr/bin/clang clang /usr/bin/clang-14 100 && \\
    update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-14 100 && \\
    update-alternatives --install /usr/bin/cc cc /usr/bin/clang-14 100 && \\
    update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++-14 100
RUN pip3 install "atheris==2.3.0"
WORKDIR /home/student
RUN git clone https://github.com/luau-lang/luau.git luau && cd luau && git checkout $VERSION
RUN cd luau && CXX=clang++-14 CC=clang-14 make -j\$(nproc) config=fuzz fuzz-compiler
DOCKERFILE

echo ""

# Create output directories
mkdir -p "$PROJECT_DIR/shared/corpus/typeck_$VERSION"
mkdir -p "$PROJECT_DIR/shared/crashes/typeck_$VERSION"

# Run the fuzzer
docker run --rm \
  -v "$PROJECT_DIR/grammar_fuzzer:/home/student/grammar_fuzzer:ro" \
  -v "$PROJECT_DIR/shared:/home/student/shared" \
  "$IMAGE_TAG" bash -c "
cd /home/student/luau

# Build the custom type checker fuzz target
cp /home/student/grammar_fuzzer/fuzz_typeck_custom.cpp fuzz/typeck_custom.cpp
clang++-14 fuzz/typeck_custom.cpp -g -Wall -fsanitize=address,fuzzer -O2 -std=c++17 \
  -ICommon/include -IAst/include -ICompiler/include -IAnalysis/include -IEqSat/include \
  -IVM/include -ICodeGen/include -IConfig/include \
  -c -o /tmp/tc.o 2>/dev/null
clang++-14 /tmp/tc.o \
  build/fuzz/libluauanalysis.a build/fuzz/libluaueqsat.a \
  build/fuzz/libluaucompiler.a build/fuzz/libluauast.a \
  build/fuzz/libluauconfig.a build/fuzz/libluaucodegen.a \
  build/fuzz/libluauvm.a \
  -fsanitize=address,fuzzer -o /tmp/ftc 2>/dev/null

if [ ! -f /tmp/ftc ]; then
  echo 'Error: Failed to build fuzz target for this Luau version'
  exit 1
fi

cd /home/student

# Generate seed corpus with the grammar
echo '=== Generating $NUM_SEEDS seed programs ==='
python3 grammar_fuzzer/generate_corpus.py \
  --count $NUM_SEEDS --max-depth 5 --seed 888 \
  --output-dir shared/corpus/typeck_seeds_$VERSION 2>&1 | tail -3

echo ''
echo '=== Step 1: Testing seeds individually ==='
crashes=0
total=0
for f in shared/corpus/typeck_seeds_$VERSION/gen_*.luau; do
  total=\$((total + 1))
  mkdir -p /tmp/single && rm -f /tmp/single/*
  cp \"\$f\" /tmp/single/
  timeout 10 /tmp/ftc /tmp/single 2>/dev/null
  exit_code=\$?
  if [ \$exit_code -eq 133 ] || [ \$exit_code -eq 134 ] || [ \$exit_code -eq 139 ]; then
    name=\$(basename \"\$f\")
    size=\$(wc -c < \"\$f\")
    echo \"  CRASH: \$name (\$size bytes) — exit \$exit_code\"
    cp \"\$f\" shared/crashes/typeck_$VERSION/
    crashes=\$((crashes + 1))
  fi
done

echo ''
echo \"Seeds: \$crashes/\$total triggered crashes\"

if [ \$crashes -eq 0 ]; then
  echo ''
  echo '=== Step 2: Running libFuzzer with mutation (${MAX_TIME}s) ==='
  timeout \$((${MAX_TIME} + 5)) /tmp/ftc \
    shared/corpus/typeck_$VERSION shared/corpus/typeck_seeds_$VERSION \
    -max_total_time=${MAX_TIME} -timeout=10 \
    -artifact_prefix=shared/crashes/typeck_$VERSION/ \
    2>&1 | tail -15
fi

echo ''
echo '=== Crash files ==='
for f in shared/crashes/typeck_$VERSION/*; do
  [ -f \"\$f\" ] && echo \"  \$(basename \$f): \$(wc -c < \$f) bytes\"
done
"
