#!/bin/bash
# Collect and summarize crash files from all fuzzing targets.
#
# Usage (inside Docker):
#   ./scripts/collect_crashes.sh

CRASHES_BASE="/home/student/shared/crashes"

echo "=== Crash Summary ==="
echo ""

total=0

for target_dir in "$CRASHES_BASE"/*/; do
    [ -d "$target_dir" ] || continue
    target=$(basename "$target_dir")

    crashes=$(find "$target_dir" -name "crash-*" 2>/dev/null | wc -l)
    ooms=$(find "$target_dir" -name "oom-*" 2>/dev/null | wc -l)
    timeouts=$(find "$target_dir" -name "timeout-*" 2>/dev/null | wc -l)
    subtotal=$((crashes + ooms + timeouts))
    total=$((total + subtotal))

    echo "--- ${target} ---"
    echo "  Crashes:  ${crashes}"
    echo "  OOMs:     ${ooms}"
    echo "  Timeouts: ${timeouts}"

    # Show details for each crash
    for crash in "$target_dir"/crash-* "$target_dir"/oom-* "$target_dir"/timeout-*; do
        [ -f "$crash" ] || continue
        size=$(wc -c < "$crash")
        echo "  $(basename "$crash"): ${size} bytes"
        # Show first 80 chars as text preview
        echo "    preview: $(head -c 80 "$crash" | tr '\0' '.' | tr '\n' ' ')"
    done
    echo ""
done

echo "=== Total: ${total} artifacts ==="
