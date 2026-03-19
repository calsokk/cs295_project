#!/bin/bash
# Doc: Natural_Language_Code/build/info_build.md
# Minimize the fuzzer corpus for a given target using libFuzzer's -merge feature.
#
# Usage (inside Docker):
#   ./scripts/minimize_corpus.sh compiler
#   ./scripts/minimize_corpus.sh parser

set -e

TARGET="${1:-compiler}"
LUAU_DIR="/home/student/luau"
CORPUS_DIR="/home/student/shared/corpus/${TARGET}"
MINIMIZED_DIR="/home/student/shared/corpus/${TARGET}_minimized"

if [ ! -f "${LUAU_DIR}/fuzz-${TARGET}" ]; then
    echo "ERROR: ${LUAU_DIR}/fuzz-${TARGET} not found"
    exit 1
fi

if [ ! -d "$CORPUS_DIR" ] || [ -z "$(ls -A "$CORPUS_DIR" 2>/dev/null)" ]; then
    echo "ERROR: Corpus directory ${CORPUS_DIR} is empty or missing"
    exit 1
fi

original_count=$(ls "$CORPUS_DIR" | wc -l)
echo "Minimizing corpus for fuzz-${TARGET}..."
echo "Original corpus: ${original_count} files"

mkdir -p "$MINIMIZED_DIR"

"${LUAU_DIR}/fuzz-${TARGET}" \
    -merge=1 \
    "$MINIMIZED_DIR" \
    "$CORPUS_DIR"

minimized_count=$(ls "$MINIMIZED_DIR" | wc -l)
echo ""
echo "=== Minimization Complete ==="
echo "Original:  ${original_count} files"
echo "Minimized: ${minimized_count} files"
echo "Output:    ${MINIMIZED_DIR}"
