"""
Generate a corpus of random valid Luau programs for seed fuzzing.

Usage:
    python3 generate_corpus.py --count 100 --output-dir ../seed_corpus/generated/
    python3 generate_corpus.py --count 1000 --max-depth 6 --output-dir /tmp/corpus
"""

import argparse
import os
import sys

from luau_grammar import LuauGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Generate random valid Luau programs for fuzzer seed corpus"
    )
    parser.add_argument("--count", type=int, default=100,
                        help="Number of programs to generate (default: 100)")
    parser.add_argument("--output-dir", type=str, default="../seed_corpus/generated",
                        help="Output directory for generated .luau files")
    parser.add_argument("--max-depth", type=int, default=5,
                        help="Maximum recursion depth (default: 5)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Generating {args.count} Luau programs (max_depth={args.max_depth})...")
    print(f"Output directory: {args.output_dir}")

    for i in range(args.count):
        seed = (args.seed + i) if args.seed is not None else None
        gen = LuauGenerator(max_depth=args.max_depth, seed=seed)
        program = gen.chunk()

        filepath = os.path.join(args.output_dir, f"gen_{i:05d}.luau")
        with open(filepath, "w") as f:
            f.write(program)

    print(f"Generated {args.count} files")

    print("\nGrammar rule coverage (least → most used):")
    for rule, count in LuauGenerator.coverage_report().items():
        bar = "#" * min(count, 60)
        print(f"  {rule:<25} {count:>5}  {bar}")

    sample_path = os.path.join(args.output_dir, "gen_00000.luau")
    if os.path.exists(sample_path):
        print(f"\nSample ({sample_path}):")
        with open(sample_path) as f:
            content = f.read()
            lines = content.split("\n")[:20]
            for line in lines:
                print(f"  {line}")
            if len(content.split("\n")) > 20:
                print("  ...")


if __name__ == "__main__":
    main()
