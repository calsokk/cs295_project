# Luau Fuzzer

Grammar-based fuzzer for the [Luau](https://github.com/luau-lang/luau) language targeting the parser, type checker, compiler, and linter. Uses a recursive descent generator to produce valid Luau programs and feeds them to Luau's libFuzzer harnesses.

## Requirements

- Docker

## Setup

```bash
./run_docker.sh
```

This builds the Docker image and drops you into a container with Luau built and ready to fuzz.

## Usage

```bash
# Inside the container — fuzz a target (parser, compiler, typeck, linter)
./scripts/run_fuzzer.sh compiler 3600   # 1 hour
./scripts/run_fuzzer.sh parser 3600
./scripts/run_fuzzer.sh typeck 3600
./scripts/run_fuzzer.sh linter 3600

# Check for crashes
./scripts/collect_crashes.sh

# Reproduce a crash
./scripts/reproduce_crash.sh compiler shared/crashes/compiler/crash-abc123

# Minimize corpus before long runs
./scripts/minimize_corpus.sh compiler
```

Crash artifacts, corpus files, and logs are saved to `shared/` on the host.

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
scripts/
    run_fuzzer.sh           # Start a libFuzzer campaign
    collect_crashes.sh      # Summarize crash artifacts
    minimize_corpus.sh      # Deduplicate corpus with libFuzzer merge
    reproduce_crash.sh      # Replay a single crash input
```

## Findings

We found an OOM bug in Luau 0.660's compiler. Programs using deeply nested type annotations combined with string interpolation, qualified generic types (`module.Type<T>`), and `type function` declarations caused the compiler to exhaust memory within ~18,000 iterations. The bug does not reproduce on Luau 0.709 or later.

The crashes were only reachable after extending the grammar from 31 to 46 rules. The original grammar was missing string interpolation (the code existed but was never called), qualified types, generic instantiation, method calls, varargs, and type function declarations. We also fixed a bug where the fuzzer was passing `--binary -` to `luau-compile`, which doesn't support stdin — every previous compiler run had been silently failing.
