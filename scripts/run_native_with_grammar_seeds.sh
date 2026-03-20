#!/bin/bash
# Run native libFuzzer binaries seeded with grammar-generated inputs.
#
# This is ~1500x faster than routing parser/typeck/linter through the
# Atheris Python wrapper (~2 exec/s → ~3000 exec/s).  Grammar-generated
# seeds give libFuzzer structurally valid starting points; libFuzzer's own
# coverage-guided mutation takes over from there.
#
# Usage (inside Docker):
#   ./scripts/run_native_with_grammar_seeds.sh parser          # 1 hour, 1 worker
#   ./scripts/run_native_with_grammar_seeds.sh typeck 7200 4   # 2 hours, 4 workers
#   ./scripts/run_native_with_grammar_seeds.sh linter 3600     # 1 hour

set -e

TARGET="${1:-parser}"
DURATION="${2:-3600}"
WORKERS="${3:-1}"
SEED_COUNT="${4:-500}"

LUAU_DIR="/home/student/luau"
GRAMMAR_DIR="/home/student/grammar_fuzzer"
CORPUS_DIR="/home/student/shared/corpus/native-${TARGET}"
CRASHES_DIR="/home/student/shared/crashes/native-${TARGET}"
SEED_DIR="/home/student/seed_corpus"
GRAMMAR_SEED_DIR="/home/student/shared/corpus/grammar-seeds-${TARGET}"
LOG_DIR="/home/student/shared/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

BINARY="${LUAU_DIR}/fuzz-${TARGET}"

# --- Validate ----------------------------------------------------------

if [ "$TARGET" = "compiler" ]; then
    echo "ERROR: 'compiler' has no native libFuzzer binary."
    echo "       Use fuzz_luau_atheris.py for compiler fuzzing."
    exit 1
fi

if [ ! -f "$BINARY" ]; then
    echo "ERROR: ${BINARY} not found"
    echo "Available targets:"
    ls "${LUAU_DIR}"/fuzz-* 2>/dev/null || echo "  (none)"
    exit 1
fi

mkdir -p "$CORPUS_DIR" "$CRASHES_DIR" "$GRAMMAR_SEED_DIR" "$LOG_DIR"

# --- Generate grammar seeds -------------------------------------------

echo "=== Generating ${SEED_COUNT} grammar seeds ==="
cd "$GRAMMAR_DIR"
python3 generate_corpus.py \
    --count "$SEED_COUNT" \
    --max-depth 5 \
    --output-dir "$GRAMMAR_SEED_DIR"
cd /home/student

echo ""
echo "=== Native libFuzzer + Grammar Seeds ==="
echo "Target:        fuzz-${TARGET}"
echo "Duration:      ${DURATION}s"
echo "Workers:       ${WORKERS}"
echo "Grammar seeds: ${GRAMMAR_SEED_DIR} (${SEED_COUNT} files)"
echo "Hand seeds:    ${SEED_DIR}"
echo "Corpus:        ${CORPUS_DIR}"
echo "Crashes:       ${CRASHES_DIR}"
echo "Log:           ${LOG_DIR}/native_${TARGET}_${TIMESTAMP}.log"
echo ""

# --- Run native libFuzzer ----------------------------------------------

DICT_FLAG=""
if [ -f "${LUAU_DIR}/fuzz/syntax.dict" ]; then
    DICT_FLAG="-dict=${LUAU_DIR}/fuzz/syntax.dict"
fi

"$BINARY" \
    "$CORPUS_DIR" \
    "$GRAMMAR_SEED_DIR" \
    "$SEED_DIR" \
    $DICT_FLAG \
    -artifact_prefix="${CRASHES_DIR}/" \
    -max_total_time="$DURATION" \
    -max_len=4096 \
    -workers="$WORKERS" \
    -jobs="$WORKERS" \
    -print_final_stats=1 \
    2>&1 | tee "${LOG_DIR}/native_${TARGET}_${TIMESTAMP}.log"

echo ""
echo "=== Fuzzing Complete ==="
echo "Crashes: $(find "$CRASHES_DIR" -name 'crash-*' -o -name 'oom-*' -o -name 'timeout-*' 2>/dev/null | wc -l)"
echo "Corpus size: $(ls "$CORPUS_DIR" 2>/dev/null | wc -l) files"
