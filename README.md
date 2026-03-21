# Luau Fuzzer

Grammar-based fuzzer for [Luau](https://github.com/luau-lang/luau) targeting the parser, type checker, compiler, and linter.

## Requirements

- Docker

## Setup

```bash
./run_docker.sh
```

## Structure

```
Dockerfile              # x86_64 build environment
Dockerfile_aarch64      # ARM64 build environment (Apple Silicon)
run_docker.sh           # Build image and start container
seed_corpus/            # Hand-written valid Luau programs
grammar_fuzzer/
    luau_grammar.py         # Recursive descent Luau program generator
    generate_corpus.py      # Batch corpus generation
    fuzz_luau_atheris.py    # Atheris coverage-guided grammar fuzzer
    fuzz_buffer_bug.py      # Targeted generator for buffer constant-folding bugs
    fuzz_typefunc_bug.py    # Targeted generator for type function crashes
    fuzz_differential.py    # Differential fuzzer for miscompilation bugs
scripts/
    run_fuzzer.sh           # Start a libFuzzer campaign
    collect_crashes.sh      # Summarize crash artifacts
    minimize_corpus.sh      # Deduplicate corpus with libFuzzer merge
    reproduce_crash.sh      # Replay a single crash input
```

## Findings

**OOM bug in Luau 0.660.** Deeply nested type annotations with string interpolation and `type function` declarations caused the compiler to exhaust memory within ~18,000 iterations. Fixed in 0.709.

**Register corruption in Luau 0.709 ([#2248](https://github.com/luau-lang/luau/issues/2248)).** Calling `string.char(unpack(tbl))` with 8+ elements corrupts a register in the fastcall fallback path, causing a runtime type error at `--!optimize 1`. Fixed in 0.710. Found using `fuzz_differential.py`.
