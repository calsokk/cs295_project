"""
Differential fuzzer for Luau miscompilation bugs (issue #2248).

Runs each generated program at --!optimize 0 and --!optimize 1 and flags
any difference in output as a bug. Targets the fastcall fallback path where
the compiler clobbers a register with GETUPVAL.

The tricky part is that most randomly generated Luau programs just crash at
runtime from nil refs or type errors, so you never get a clean divergence.
To fix this we always generate a program shaped like:

    local string = string
    local tbl = {8+ numbers}
    local function f(t) return string.char(unpack(t)) end
    print(f(tbl))

and vary the builtin, table size, element values, and call site shape.

Usage:
    python3 fuzz_differential.py
    python3 fuzz_differential.py --iters 500 --seed 42
    LUAU_BIN=/path/to/luau python3 fuzz_differential.py
"""

import argparse
import os
import random
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))
from luau_grammar import LuauGenerator

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LUAU_BIN = os.environ.get(
    "LUAU_BIN",
    os.path.join(os.path.dirname(__file__), "..", "luau", "build", "debug", "luau"),
)
CRASH_DIR = os.environ.get(
    "CRASH_DIR",
    os.path.join(os.path.dirname(__file__), "..", "shared", "crashes", "differential"),
)
RUN_TIMEOUT = 5
REPORT_EVERY = 200

# ---------------------------------------------------------------------------
# Builtins that use the FASTCALL path at opt >= 1.
# Each entry is (lib_to_shadow, dotted_call, arg_kind) where arg_kind
# controls what values go in the table so we don't get type errors:
#   "byte" = 1-127 ints  (string.char)
#   "num"  = any number  (math builtins)
#   "uint" = 0-65535     (bit32 builtins)
# ---------------------------------------------------------------------------
_FASTCALL_CATALOGUE = [
    # string builtins — string.char needs byte-range ints
    ("string", "string.char",    "byte"),
    ("string", "string.byte",    "byte"),   # string.byte(s, i, j) — fewer args fine
    # math builtins accept any numbers
    ("math",   "math.max",       "num"),
    ("math",   "math.min",       "num"),
    ("math",   "math.abs",       "num"),    # unary but variadic unpack still tests fallback
    # bit32 builtins want unsigned ints
    ("bit32",  "bit32.band",     "uint"),
    ("bit32",  "bit32.bor",      "uint"),
    ("bit32",  "bit32.bxor",     "uint"),
]


def _make_args(kind: str, count: int) -> list:
    if kind == "byte":
        return [str(random.randint(1, 127)) for _ in range(count)]
    elif kind == "uint":
        return [str(random.randint(0, 0xFFFF)) for _ in range(count)]
    else:
        return [str(random.randint(-1000, 1000)) for _ in range(count)]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class DifferentialGenerator(LuauGenerator):

    def chunk(self) -> str:
        lib, fn, kind = random.choice(_FASTCALL_CATALOGUE)

        # always > 7 elements so the fastcall limit is exceeded and the fallback fires
        count = random.randint(8, 12)
        elems = _make_args(kind, count)
        tbl_lit = "{" + ", ".join(elems) + "}"

        tbl_var  = self._fresh_var()
        func_var = self._fresh_var()
        res_var  = self._fresh_var()

        lines = []

        # shadow the global lib as a local upvalue — this is what GETUPVAL clobbers
        if random.random() < 0.85:
            self._defined_vars.append(lib)
            lines.append(f"local {lib} = {lib}")

        lines.append(f"local {tbl_var} = {tbl_lit}")

        # vary the call site shape to hit different register allocation scenarios
        call_shape = random.randint(0, 2)
        if call_shape == 0:
            lines.append(f"local function {func_var}(t)")
            lines.append(f"  return {fn}(unpack(t))")
            lines.append(f"end")
            lines.append(f"local {res_var} = {func_var}({tbl_var})")
        elif call_shape == 1:
            lines.append(f"local {res_var} = {fn}(unpack({tbl_var}))")
        else:
            lines.append(f"local {res_var} = (function(t) return {fn}(unpack(t)) end)({tbl_var})")

        # print the result so the optimizer can't dead-code-eliminate the call
        lines.append(f"print(type({res_var}), tostring({res_var}):sub(1, 40))")

        if random.random() < 0.4:
            extra = self._safe_extra(tbl_var, fn, kind)
            if extra:
                lines.extend(extra)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _safe_extra(self, tbl_var: str, fn: str, kind: str) -> list:
        # a few extra statements that are safe to append without causing runtime errors
        out = []
        choice = random.randint(0, 3)
        if choice == 0:
            # Second call with a freshly built table
            count2 = random.randint(8, 12)
            elems2 = _make_args(kind, count2)
            v = self._fresh_var()
            out.append(f"local {v} = {fn}(unpack({{{', '.join(elems2)}}}))")
            out.append(f"print(type({v}))")
        elif choice == 1:
            # Table length check
            out.append(f"print(#{tbl_var})")
        elif choice == 2:
            # ipairs over the table
            kv = self._fresh_var()
            out.append(f"for _, {kv} in ipairs({tbl_var}) do end")
        # choice == 3: nothing extra
        return out


# ---------------------------------------------------------------------------
# Differential oracle
# ---------------------------------------------------------------------------

def _run(luau_bin: str, program: str, opt_level: int):
    """Run the program at the given opt level, returns (stdout, stderr, rc) or (None, None, None) on timeout."""
    source = f"--!optimize {opt_level}\n{program}"
    with tempfile.NamedTemporaryFile(suffix=".luau", delete=False, mode="w") as f:
        f.write(source)
        path = f.name
    try:
        result = subprocess.run(
            [luau_bin, path],
            capture_output=True,
            timeout=RUN_TIMEOUT,
            text=True,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return None, None, None
    finally:
        os.unlink(path)


def _is_divergence(r0, r1) -> bool:
    out0, _err0, rc0 = r0
    out1, _err1, rc1 = r1
    if out0 is None or out1 is None:
        return False   # timeout
    # One succeeded, the other didn't → miscompilation
    if (rc0 == 0) != (rc1 == 0):
        return True
    # Both succeeded but produced different output → miscompilation
    if rc0 == 0 and out0 != out1:
        return True
    return False


def _save(program: str, r0, r1, idx: int) -> str:
    os.makedirs(CRASH_DIR, exist_ok=True)
    h = hash(program) & 0xFFFFFFFF
    path = os.path.join(CRASH_DIR, f"diff-{idx:06d}-{h:08x}.luau")
    out0, err0, rc0 = r0
    out1, err1, rc1 = r1
    with open(path, "w") as f:
        f.write("-- DIFFERENTIAL FINDING\n")
        f.write(f"-- opt0: rc={rc0}  stdout={out0!r}  stderr={err0!r}\n")
        f.write(f"-- opt1: rc={rc1}  stdout={out1!r}  stderr={err1!r}\n")
        f.write("--\n")
        f.write(program)
    return path


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--iters", type=int, default=0,    help="iterations (0 = forever)")
    ap.add_argument("--seed",  type=int, default=None, help="random seed")
    ap.add_argument("--depth", type=int, default=5,    help="max grammar depth")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    luau_bin = os.path.abspath(LUAU_BIN)
    if not os.path.isfile(luau_bin):
        sys.exit(f"luau binary not found: {luau_bin}\nBuild it first or set LUAU_BIN.")

    print(f"binary  : {luau_bin}")
    print(f"crashes : {os.path.abspath(CRASH_DIR)}")
    print(f"depth   : {args.depth}")
    print(f"iters   : {'∞' if not args.iters else args.iters}")
    print()

    found = timeouts = errors_both = i = 0
    t0 = time.time()

    while True:
        if args.iters and i >= args.iters:
            break
        i += 1

        gen = DifferentialGenerator(max_depth=args.depth)
        try:
            program = gen.chunk()
        except Exception:
            continue
        if not program.strip():
            continue

        r0 = _run(luau_bin, program, 0)
        r1 = _run(luau_bin, program, 1)

        if r0[0] is None or r1[0] is None:
            timeouts += 1
            continue

        # Track programs that error under both (not bugs, just noise)
        if r0[2] != 0 and r1[2] != 0:
            errors_both += 1

        if _is_divergence(r0, r1):
            found += 1
            path = _save(program, r0, r1, i)
            print(f"\n*** DIVERGENCE #{found} at iter {i}")
            print(f"    opt0 rc={r0[2]}  stdout={r0[0]!r}")
            print(f"    opt1 rc={r1[2]}  stdout={r1[0]!r}")
            print(f"    saved: {path}")

        if i % REPORT_EVERY == 0:
            elapsed = time.time() - t0
            print(
                f"[{i:>7}]  {i/elapsed:5.0f} iter/s  "
                f"found={found}  timeouts={timeouts}  both_err={errors_both}"
            )

    elapsed = time.time() - t0
    print(f"\nDone. {i} iters in {elapsed:.1f}s  |  divergences: {found}")


if __name__ == "__main__":
    main()
