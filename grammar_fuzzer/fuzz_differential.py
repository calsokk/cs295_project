import argparse
import os
import random
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))
from luau_grammar import LuauGenerator

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

_FASTCALL_CATALOGUE = [
    ("string", "string.char",  "byte"),
    ("string", "string.byte",  "byte"),
    ("math",   "math.max",     "num"),
    ("math",   "math.min",     "num"),
    ("math",   "math.abs",     "num"),
    ("bit32",  "bit32.band",   "uint"),
    ("bit32",  "bit32.bor",    "uint"),
    ("bit32",  "bit32.bxor",   "uint"),
]


def _make_args(kind, count):
    if kind == "byte":
        return [str(random.randint(1, 127)) for _ in range(count)]
    elif kind == "uint":
        return [str(random.randint(0, 0xFFFF)) for _ in range(count)]
    else:
        return [str(random.randint(-1000, 1000)) for _ in range(count)]


class DifferentialGenerator(LuauGenerator):

    def chunk(self):
        lib, fn, kind = random.choice(_FASTCALL_CATALOGUE)

        count = random.randint(8, 12)  # > 7 so the fastcall limit is always exceeded
        elems = _make_args(kind, count)
        tbl_lit = "{" + ", ".join(elems) + "}"

        tbl_var  = self._fresh_var()
        func_var = self._fresh_var()
        res_var  = self._fresh_var()

        lines = []

        if random.random() < 0.85:  # shadow the global as a local upvalue
            self._defined_vars.append(lib)
            lines.append(f"local {lib} = {lib}")

        lines.append(f"local {tbl_var} = {tbl_lit}")

        # vary call site shape to hit different register allocation scenarios
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

        # print so the optimizer can't eliminate the call
        lines.append(f"print(type({res_var}), tostring({res_var}):sub(1, 40))")

        if random.random() < 0.4:
            lines.extend(self._safe_extra(tbl_var, fn, kind))

        return "\n".join(lines)

    def _safe_extra(self, tbl_var, fn, kind):
        choice = random.randint(0, 3)
        if choice == 0:
            elems2 = _make_args(kind, random.randint(8, 12))
            v = self._fresh_var()
            return [
                f"local {v} = {fn}(unpack({{{', '.join(elems2)}}}))",
                f"print(type({v}))",
            ]
        elif choice == 1:
            return [f"print(#{tbl_var})"]
        elif choice == 2:
            kv = self._fresh_var()
            return [f"for _, {kv} in ipairs({tbl_var}) do end"]
        return []


def _run(luau_bin, program, opt_level):
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


def _is_divergence(r0, r1):
    out0, _err0, rc0 = r0
    out1, _err1, rc1 = r1
    if out0 is None or out1 is None:
        return False
    if (rc0 == 0) != (rc1 == 0):
        return True
    if rc0 == 0 and out0 != out1:
        return True
    return False


def _save(program, r0, r1, idx):
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=0)
    ap.add_argument("--seed",  type=int, default=None)
    ap.add_argument("--depth", type=int, default=5)
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    luau_bin = os.path.abspath(LUAU_BIN)
    if not os.path.isfile(luau_bin):
        sys.exit(f"luau binary not found: {luau_bin}")

    print(f"binary  : {luau_bin}")
    print(f"crashes : {os.path.abspath(CRASH_DIR)}")
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
            print(f"[{i:>7}]  {i/elapsed:5.0f} iter/s  found={found}  timeouts={timeouts}  both_err={errors_both}")

    elapsed = time.time() - t0
    print(f"\nDone. {i} iters in {elapsed:.1f}s  |  divergences: {found}")


if __name__ == "__main__":
    main()
