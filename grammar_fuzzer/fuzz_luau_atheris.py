# Doc: Natural_Language_Code/fuzzing/info_fuzzing_grammar.md
"""
Coverage-guided grammar-based fuzzer using Atheris.
 
Generates syntactically valid Luau programs using FuzzedDataProvider
and runs them against a Luau target binary. Atheris tracks coverage
to guide mutation toward interesting inputs.

Usage (inside Docker):
    python3 fuzz_luau_atheris.py <corpus_dir>
    python3 fuzz_luau_atheris.py <corpus_dir> -max_total_time=3600

    # Target a specific component (default: compiler)
    TARGET=parser  python3 fuzz_luau_atheris.py <corpus_dir>
    TARGET=typeck  python3 fuzz_luau_atheris.py <corpus_dir>
    TARGET=linter  python3 fuzz_luau_atheris.py <corpus_dir>
    TARGET=compiler python3 fuzz_luau_atheris.py <corpus_dir>
"""

import signal
import sys
import subprocess
import tempfile
import os
import time

import atheris

# Must instrument before importing our modules
with atheris.instrument_imports():
    from luau_grammar import LuauGenerator

LUAU_DIR = "/home/student/luau"

# Which component to fuzz. "compiler" uses luau-compile via stdin.
# parser/typeck/linter use their libFuzzer binaries in single-input mode.
TARGET = os.environ.get("TARGET", "compiler")

# Map target name to binary path
_TARGET_BINARIES = {
    "compiler": os.environ.get("LUAU_COMPILE", f"{LUAU_DIR}/luau-compile"),
    "parser":   f"{LUAU_DIR}/fuzz-parser",
    "typeck":   f"{LUAU_DIR}/fuzz-typeck",
    "linter":   f"{LUAU_DIR}/fuzz-linter",
}

if TARGET not in _TARGET_BINARIES:
    raise ValueError(f"Unknown TARGET={TARGET!r}. Choose from: {list(_TARGET_BINARIES)}")

TARGET_BINARY = _TARGET_BINARIES[TARGET]

COMPILE_TIMEOUT = 5
REPORT_INTERVAL = 500
COVERAGE_LOG = os.environ.get(
    "GRAMMAR_COVERAGE_LOG",
    f"/home/student/shared/logs/grammar_coverage_{TARGET}.txt"
)

_call_count = 0
_start_time = time.time()

# Per-rule compile outcome counters: {rule: [ok_count, total_count]}
_rule_compile: dict = {}


def _run_target(program: str):
    """Run the target binary on program. Returns subprocess.CompletedProcess."""
    encoded = program.encode("utf-8", errors="replace")

    if TARGET == "compiler":
        # luau-compile reads from stdin
        return subprocess.run(
            [TARGET_BINARY, "--binary", "-"],
            input=encoded,
            capture_output=True,
            timeout=COMPILE_TIMEOUT,
        )
    else:
        # fuzz-parser/typeck/linter take a file path in single-input mode
        with tempfile.NamedTemporaryFile(suffix=".luau", delete=False) as f:
            f.write(encoded)
            tmppath = f.name
        try:
            return subprocess.run(
                [TARGET_BINARY, tmppath],
                capture_output=True,
                timeout=COMPILE_TIMEOUT,
            )
        finally:
            os.unlink(tmppath)


def _record_compile(rules_used, success):
    for rule in rules_used:
        entry = _rule_compile.setdefault(rule, [0, 0])
        if success:
            entry[0] += 1
        entry[1] += 1


def _write_coverage_report():
    os.makedirs(os.path.dirname(COVERAGE_LOG), exist_ok=True)
    report = LuauGenerator.coverage_report()
    total_hits = sum(report.values()) or 1
    elapsed = time.time() - _start_time

    lines = [
        f"target     : {TARGET} ({TARGET_BINARY})",
        f"iterations : {_call_count}",
        f"elapsed    : {elapsed:.0f}s",
        f"updated    : {time.strftime('%H:%M:%S')}",
        "",
        f"{'rule':<25} {'hits':>6}  {'share':>5}  {'ok%':>5}  note",
        "-" * 65,
    ]
    for rule, count in report.items():
        share = count / total_hits * 100
        entry = _rule_compile.get(rule, [0, 0])
        ok_pct = entry[0] / entry[1] * 100 if entry[1] else 0
        note = " <-- high impact" if ok_pct >= 50 else ""
        lines.append(
            f"{rule:<25} {count:>6}  {share:>4.1f}%  {ok_pct:>4.1f}%{note}"
        )

    with open(COVERAGE_LOG, "w") as f:
        f.write("\n".join(lines) + "\n")


def _sigusr1_handler(signum, frame):
    _write_coverage_report()


signal.signal(signal.SIGUSR1, _sigusr1_handler)


def TestOneInput(data):
    """Atheris entry point: generate a Luau program and run it against the target."""
    global _call_count

    _call_count += 1

    # Snapshot rule counts before generation to isolate this call's usage
    before = dict(LuauGenerator._rule_counts)

    fdp = atheris.FuzzedDataProvider(data)
    gen = LuauGenerator(provider=fdp, max_depth=5)

    try:
        program = gen.chunk()
    except Exception:
        return

    if not program.strip():
        return

    after = LuauGenerator._rule_counts
    rules_used = {r for r in after if after[r] > before.get(r, 0)}

    if _call_count % REPORT_INTERVAL == 0:
        _write_coverage_report()

    try:
        result = _run_target(program)
        success = result.returncode == 0
        _record_compile(rules_used, success)

        if result.returncode < 0:
            crash_dir = os.environ.get(
                "CRASH_DIR", f"/home/student/shared/crashes/grammar-{TARGET}"
            )
            os.makedirs(crash_dir, exist_ok=True)
            crash_file = os.path.join(
                crash_dir,
                f"crash-{TARGET}-{abs(result.returncode)}-{hash(program) & 0xFFFF:04x}.luau"
            )
            with open(crash_file, "w") as f:
                f.write(program)
            raise RuntimeError(
                f"{TARGET_BINARY} crashed with signal {-result.returncode}"
            )
    except subprocess.TimeoutExpired:
        _record_compile(rules_used, False)
    except RuntimeError:
        raise
    except Exception:
        pass


def main():
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
