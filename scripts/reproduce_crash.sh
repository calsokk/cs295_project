#!/bin/bash
# Doc: Natural_Language_Code/build/info_build.md
# Reproduce a single crash for debugging and analysis.
#
# Usage (inside Docker):
#   ./scripts/reproduce_crash.sh compiler shared/crashes/compiler/crash-abc123
#   ./scripts/reproduce_crash.sh parser shared/crashes/parser/crash-def456

TARGET="${1:-compiler}"
CRASH_FILE="$2"
LUAU_DIR="/home/student/luau"

if [ -z "$CRASH_FILE" ]; then
    echo "Usage: ./scripts/reproduce_crash.sh <target> <crash_file>"
    echo ""
    echo "Targets: parser, compiler, typeck, linter"
    echo ""
    echo "Available crash files:"
    find /home/student/shared/crashes -type f -name "crash-*" -o -name "oom-*" -o -name "timeout-*" 2>/dev/null
    exit 1
fi

if [ ! -f "$CRASH_FILE" ]; then
    echo "ERROR: Crash file not found: ${CRASH_FILE}"
    exit 1
fi

if [ ! -f "${LUAU_DIR}/fuzz-${TARGET}" ]; then
    echo "ERROR: ${LUAU_DIR}/fuzz-${TARGET} not found"
    exit 1
fi

echo "=== Reproducing Crash ==="
echo "Target: fuzz-${TARGET}"
echo "File:   ${CRASH_FILE}"
echo "Size:   $(wc -c < "$CRASH_FILE") bytes"
echo ""
echo "--- Input Content ---"
xxd "$CRASH_FILE" | head -30
echo ""
echo "--- Text Preview ---"
head -c 500 "$CRASH_FILE" | tr '\0' '.'
echo ""
echo ""
echo "--- Running Fuzzer ---"
"${LUAU_DIR}/fuzz-${TARGET}" "$CRASH_FILE"
