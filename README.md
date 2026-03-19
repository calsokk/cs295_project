# Luau Fuzzer

Grammar-based + greybox fuzzing of the [Luau](https://github.com/luau-lang/luau) compiler and analysis tools using libFuzzer + AddressSanitizer.

## Requirements

- Docker

## Usage

```bash
# Build the Docker image and start the container
./run_docker.sh

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

Crash artifacts, corpus, and logs are written to `shared/` on the host machine.

## Structure

```
Dockerfile              # x86_64 build environment
Dockerfile_aarch64      # ARM64 build environment (Apple Silicon)
run_docker.sh           # Build image and start container
seed_corpus/            # Hand-written valid Luau programs
grammar_fuzzer/
    luau_grammar.py     # Recursive descent Luau program generator
    generate_corpus.py  # Batch corpus generation
    fuzz_luau_atheris.py# Atheris coverage-guided grammar fuzzer
scripts/
    run_fuzzer.sh       # Start a libFuzzer campaign
    collect_crashes.sh  # Summarize crash artifacts
    minimize_corpus.sh  # Deduplicate corpus with libFuzzer merge
    reproduce_crash.sh  # Replay a single crash input
```
