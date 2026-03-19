#!/bin/bash
# Doc: Natural_Language_Code/build/info_build.md
# Start a libFuzzer fuzzing campaign for a Luau target.
#
# Usage (inside Docker):
#   ./scripts/run_fuzzer.sh parser         # Fuzz parser for 1 hour
#   ./scripts/run_fuzzer.sh compiler 7200  # Fuzz compiler for 2 hours
#   ./scripts/run_fuzzer.sh typeck 3600 4  # Fuzz typechecker, 4 workers

set -e

TARGET="${1:-compiler}"
DURATION="${2:-3600}"
WORKERS="${3:-1}"

LUAU_DIR="/home/student/luau"
CORPUS_DIR="/home/student/shared/corpus/${TARGET}"
CRASHES_DIR="/home/student/shared/crashes/${TARGET}"
SEED_DIR="/home/student/seed_corpus"
LOG_DIR="/home/student/shared/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Verify fuzzer binary exists
if [ ! -f "${LUAU_DIR}/fuzz-${TARGET}" ]; then
    echo "ERROR: ${LUAU_DIR}/fuzz-${TARGET} not found"
    echo "Available targets:"
    ls "${LUAU_DIR}"/fuzz-* 2>/dev/null || echo "  (none)"
    exit 1
fi

mkdir -p "$CORPUS_DIR" "$CRASHES_DIR" "$LOG_DIR"

echo "=== Luau Fuzzing Campaign ==="
echo "Target:   fuzz-${TARGET}"
echo "Duration: ${DURATION}s"
echo "Workers:  ${WORKERS}"
echo "Corpus:   ${CORPUS_DIR}"
echo "Crashes:  ${CRASHES_DIR}"
echo "Log:      ${LOG_DIR}/fuzz_${TARGET}_${TIMESTAMP}.log"
echo ""

DICT_FLAG=""
if [ -f "${LUAU_DIR}/fuzz/syntax.dict" ]; then
    DICT_FLAG="-dict=${LUAU_DIR}/fuzz/syntax.dict"
fi

"${LUAU_DIR}/fuzz-${TARGET}" \
    "$CORPUS_DIR" \
    "$SEED_DIR" \
    $DICT_FLAG \
    -artifact_prefix="${CRASHES_DIR}/" \
    -max_total_time="$DURATION" \
    -max_len=4096 \
    -workers="$WORKERS" \
    -jobs="$WORKERS" \
    -print_final_stats=1 \
    2>&1 | tee "${LOG_DIR}/fuzz_${TARGET}_${TIMESTAMP}.log"

echo ""
echo "=== Fuzzing Complete ==="
echo "Crashes: $(find "$CRASHES_DIR" -name 'crash-*' -o -name 'oom-*' -o -name 'timeout-*' 2>/dev/null | wc -l)"
echo "Corpus size: $(ls "$CORPUS_DIR" 2>/dev/null | wc -l) files"
