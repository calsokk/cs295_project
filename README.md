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

