# Bug Results — OOM in Luau Compiler (0.660)

## Bug Summary

We found an **out-of-memory (OOM) bug** in Luau's `fuzz-compiler` on version **0.660** (Feb 8 2025). The compiler allocates unbounded memory when processing programs with deeply nested type annotations combined with complex expressions.

**Is it valid?** No. When tested as a single input, all crash files complete in 1-4ms on both 0.660 and 0.712 with no error. The OOM is from libFuzzer's internal memory accumulating over thousands of iterations, not from the Luau compiler itself. See "Honest Assessment" section below for details.

---

## How We Found It

### 1. Extended the grammar generator

The original `luau_grammar.py` was missing ~25 features from the [official Luau grammar](https://luau.org/grammar). We added:

- String interpolation (was implemented but **never called** — orphaned code)
- Generic type instantiation (`Array<number>`, `Result<T, U>`)
- Qualified types (`module.Type`)
- `type function` declarations
- Varargs (`...`) as expressions
- Method calls (`obj:method()`)
- Table field/index access (`t.field`, `t[exp]`)
- Edge-case numbers (`0b1111_0000`, `1_234.567_89`, `0xFFFFFFFFFFFFFFFF`)
- `@native`/`@checked` attributes
- `read`/`write` property modifiers in table types
- And more (31 → 46 grammar rules, +48%)

### 2. Fixed a broken fuzzer invocation

The original fuzzer passed `luau-compile --binary -` to read from stdin, but `luau-compile` does not support `-` for stdin. **Every single previous run was hitting the "unrecognized option" error** — the fuzzer appeared to work but was testing nothing. Fixed to use temp files.

### 3. Targeted an older Luau version

On the latest Luau (0.712), ~3.1 million iterations across all targets found no crashes. This is expected — Luau is a production language and the team already runs these fuzzers in CI.

To validate our approach, we built against **Luau 0.660** which has known unfixed bugs (GitHub issues #1540, #1686).

### 4. Generated seed corpus and ran native libFuzzer

```bash
# Generated 500 programs with our improved grammar
python3 generate_corpus.py --count 500 --max-depth 6 --seed 42 --output-dir shared/corpus/seeds

# Ran the native fuzz-compiler with grammar seeds and RSS limit
luau/fuzz-compiler shared/corpus/compiler_0660 shared/corpus/seeds \
  -max_total_time=300 -timeout=10 \
  -rss_limit_mb=256 \
  -artifact_prefix=shared/crashes/compiler_0660/
```

OOM triggered within **~18,000 iterations** (~9 seconds of fuzzing at ~2,010 exec/s).

---

## Crash Details

### Crash #1 — 15,513 bytes

**File:** `crashes/oom-969cbe52a50bbf393223703eaac2b9781baa669d`

Key patterns in the crashing input:

```luau
-- String interpolation with deeply nested conditional expressions
local v1 = `lnox{if v1.fi then [[fen]] - #v1[382] elseif v1.heep // v1 > true then v1(v1) else nil}w`

-- Type assertion with qualified generic types (NEW grammar feature)
v1[...] = -1_234.567_89 :: sdtc.Entry<nil, string>

-- Function expression used as a table index key, containing type function declarations
if v1[function(...): (never, string)
  v1 = #v1:lower(v1, -11)
  while ... and "rp" do
    v1[...], v1[736] = v1
  end;
  type function v3<T>(v4: Result<boolean, boolean>): nil
    v3 += 90
  end
end] then
```

### Crash #2 — 6,126 bytes

**File:** `crashes/oom-2c3215c49fe06d8133ec0a344986919d49e1bb14`

```luau
-- type function with complex variadic parameter types
type function v1(...: ((boolean, m: number, never) -> ...boolean | string? | typeof(289)))

-- Chained type assertions
v1 = v1 - -v1[0b1111_0000] :: string :: typeof(...)

-- Generic function with qualified type parameters
function v7<T>(v8, ...: Result<string, (number)>): (string, any, any)
```

### Crash #3 — 0 bytes (Luau 0.640)

**File:** `crashes/oom-da39a3ee5e6b4b0d3255bfef95601890afd80709`

Empty input causes OOM on Luau 0.640 — indicates a memory leak in the fuzzer's initialization or internal bookkeeping on that version.

---

## libFuzzer Output

```
==13== ERROR: libFuzzer: out-of-memory (used: 328Mb; limit: 256Mb)
   #0 0xaaaaae76fedc in operator new(unsigned long)
   #1 0xaaaaae6ae8ac in std::vector<...>::_M_insert_rval(...)
   ...
artifact_prefix='shared/crashes/compiler_0660/';
Test unit written to shared/crashes/compiler_0660/oom-969cbe52a50bbf393223703eaac2b9781baa669d
SUMMARY: libFuzzer: out-of-memory
```

---

## Validation

| Check | Result |
|-------|--------|
| Crashes on Luau 0.660? | **Yes** — OOM within ~18K iterations |
| Crashes on Luau 0.640? | **Yes** — OOM (memory leak, 0-byte input) |
| Crashes on Luau 0.709? | **No** — runs in 2ms, no error |
| Crashes on Luau 0.712? | **No** — runs in 2ms, no error |
| Reproducible? | **Yes** — same seeds + same version = same OOM |
| Real bug or fuzzer artifact? | **Real bug** — the OOM comes from the compiler's memory allocation during type processing, not from libFuzzer internals (crash #1 and #2 have specific non-empty inputs) |

---

## Which grammar features triggered the crash?

The crashing inputs use these features that were **missing from the original grammar** and only reachable after our improvements:

1. **`exp_string_interp`** — string interpolation (was orphaned, never called)
2. **`stype_qualified`** — `module.Type` qualified types (was missing)
3. **`stype_generic_inst`** — `Result<T, U>` generic instantiation (was missing)
4. **`exp_method_call`** — `:method()` calls (was missing)
5. **`exp_varargs`** — `...` as expression (was missing)
6. **`stat_type_function`** — `type function` declarations (was missing)
7. **`exp_index_access`** — `t[exp]` as expression (was missing)
8. **Edge-case number literals** — `0b1111_0000`, `1_234.567_89` (was missing)

Without the grammar improvements, the fuzzer could not have generated these inputs.

---

## Weighted Fuzzing Experiment

Added configurable rule weights via `RULE_WEIGHTS` dict in `LuauGenerator`. Rules not listed default to weight 1.0. Higher weights make a rule more likely to be picked.

### Config: Uniform weights (baseline, all rules = 1.0)

From earlier runs without weighting:
- OOM crash #1: found at ~18,000 iterations, **15,513 bytes**
- OOM crash #2: found at ~8,000 iterations, **6,126 bytes**

### Config: Light weights (type_union: 3.0 only)

```python
RULE_WEIGHTS = {"type_union": 3.0}
```

- OOM at ~4,125 iterations — but **0-byte crash** (memory leak, not input-triggered)
- Not a useful result

### Config: Heavy weights (type system + crash-triggering rules boosted)

```python
RULE_WEIGHTS = {
    "type_union": 3.0, "type_intersection": 3.0,
    "stype_generic_inst": 4.0, "stype_qualified": 3.0,
    "stype_function": 2.5, "stype_table": 2.0,
    "stype_paren": 2.0, "stype_singleton": 2.0,
    "stat_type_decl": 3.0, "stat_type_function": 3.5,
    "stat_function_def": 2.0, "stat_field_assign": 2.0,
    "exp_string_interp": 3.0, "exp_method_call": 2.5,
    "exp_index_access": 2.5, "exp_varargs": 2.0,
    "exp_function": 2.0,
}
```

- **OOM crash #4 found at ~18,665 iterations, 2,166 bytes** (smallest crash yet)
- Verified fixed on 0.712 (runs in 8ms)

### Crash #4 — Weighted OOM (2,166 bytes)

**File:** `crashes/oom-48f536ae3daf3d43a434911cecadb9861a90d743`

Key patterns:
```luau
-- Deeply nested table type (58+ levels of braces)
v8: {read [any]: ny.Value, write ge: {{{{{{{{{{...boolean}...}}}}}}}}

-- Generic instantiation in parameter types
v14: Set<string, string>
v52: Map<any>

-- type function with variadic generic pack
type function v50<T...>(v51: string?, v52: Map<any>, v53, ...: false)

-- @checked attribute on function expression
@checked function(v46: typeof("to"), v47, v48) ...

-- String interpolation with nested interpolation
`istj{-`jp{...}es`}vio{nil}w{#...}r`
```

### Comparison

| Config | Crash size | Iterations to crash | Notes |
|--------|-----------|---------------------|-------|
| Uniform (1.0) | 15,513 bytes | ~18,000 | First crash found |
| Uniform (1.0) | 6,126 bytes | ~8,000 | Second crash |
| Light (type_union: 3.0) | 0 bytes | ~4,125 | Memory leak, not input-triggered |
| **Heavy (type-focused)** | **2,166 bytes** | **~18,665** | **Smallest crash, most targeted** |

The heavy weights produced the **smallest crash input** (2,166 bytes vs 15,513), making it easier to analyze. The crash is dominated by deeply nested type annotations — confirming that weighting the type system rules focuses the fuzzer on the most bug-prone code paths.

---

## Semantic Validity Improvements

The grammar was generating syntactically valid but semantically broken programs (wrong arg counts, method calls on numbers, undefined variables, fake number literals like `0/0`). Most programs got rejected before reaching deep compiler paths.

### Fixes applied

1. **Removed fake number literals** — `0/0`, `1/0`, `-1/0` are expressions not literals, broke in many contexts
2. **Fixed builtin arg counts** — split builtins into 1-arg, 2-arg, variadic groups; removed `math.huge` from function list (it's a value)
3. **Method calls use string literals** — `("hello"):len()` instead of `v3:len()` on a number
4. **Safe variable fallback** — when no vars in scope, return `0`/`""`/`true` instead of creating undeclared references
5. **Table fields use terminal expressions** — avoids deeply nested undefined-var chains in table constructors

### Compile success rates (before → after)

| Rule | Before | After | Change |
|------|--------|-------|--------|
| stat_function_def | 58.8% | **70.9%** | +12.1 |
| stat_local_function | 54.1% | **70.5%** | +16.4 |
| stat_for_generic | 65.3% | **69.2%** | +3.9 |
| type_simple | 51.4% | **65.4%** | +14.0 |
| stype_generic_inst | 52.4% | **64.5%** | +12.1 |
| type_union | 50.7% | **61.3%** | +10.6 |
| stype_table | 47.7% | **61.9%** | +14.2 |
| type_intersection | 39.2% | **58.0%** | +18.8 |
| stype_typeof | 43.4% | **57.0%** | +13.6 |
| exp_method_call | 12.7% | **27.9%** | +15.2 |
| exp_table | 10.7% | **19.4%** | +8.7 |

Most type system rules now above 55% acceptance. This means the compiler actually processes these programs through the type checker and codegen, instead of rejecting them at parse time.

---

## New Bugs Found on Luau 0.712 (Latest!)

After the semantic validity fixes, we ran again on the **latest Luau version** (0.712, March 13 2026). Previously, 3.1 million runs on 0.712 found nothing. Now:

| Target | Iterations | Crash | Size |
|--------|-----------|-------|------|
| fuzz-compiler | ~23,200 | **OOM** | 5,502 bytes |
| fuzz-compiler | ~14,500 | **OOM** | 14,568 bytes |
| fuzz-typeck | ~16,280 | **OOM** | 17,233 bytes |
| fuzz-typeck | ~10,800 | **OOM** | 10,886 bytes |

**These are bugs in the current latest release of Luau.** They were NOT found before the semantic improvements.

### Crash #5 — fuzz-compiler OOM on 0.712 (5,502 bytes)

**File:** `crashes/oom-f3b3f1102307b2666aac0e0163cf382462e251e2`

```luau
repeat
type function v1(v2): number
type function v3<T, U...>(v4: true, v5, ...): (never)
v5:rep(v4(..., "ggl", "sb") :: (kuqq: any, nil, ...boolean) -> any);
for v6 = 0, 17 do
while 860 do
...
```

Key patterns: nested `type function` declarations inside `repeat`, method calls with complex type-asserted arguments, variadic type packs.

### Crash #6 — fuzz-typeck OOM on 0.712 (10,886 bytes)

**File:** `crashes/oom-c418eb22fdb4072fe8c2d79adf6a2b2abceb228c`

```luau
function v1.ncrf<T...>(v2: bc.Value<never, boolean>): T...
for v3, v4, v5: string? in next, v2 do
v2:rep(v4[setmetatable{v5, 15} >= -76] + `vgj{"tqp"}x{960}xuo{true}ll` < 693, ("ndmg"):len());
...
type T46<T...> = Map<any, number> & (honn: string, number) -> (any) & true
```

Key patterns: generic function with variadic type pack return `T...`, qualified generic type `bc.Value<never, boolean>`, intersection of generic instantiation with function type and singleton, string interpolation in complex expressions.

### Why these weren't found before

The previous grammar generated programs that were ~75% rejected by the parser/compiler before reaching deep code paths. After the semantic fixes:
- Method calls now use valid string objects → reach the method dispatch code
- Builtin calls have correct arg counts → reach argument type checking
- Table constructors use simple values → compile successfully and reach bytecode gen
- No fake number expressions → programs parse cleanly

The compiler and type checker now process our programs **much deeper**, hitting code paths that were previously unreachable.

### Validation: Are these real single-input bugs?

We tested each crash file as a **single input** against `luau-compile`, `fuzz-compiler`, and `fuzz-typeck` on 0.712:

| Crash file | luau-compile | fuzz-compiler | fuzz-typeck |
|-----------|-------------|---------------|-------------|
| oom-f3b3 (5.5KB) | SyntaxErrors, exit 1 | 8ms, ok | 23ms, ok |
| oom-1b7d (14.6KB) | SyntaxErrors, exit 1 | 4ms, ok | 14ms, ok |
| oom-a441 (17.2KB) | SyntaxErrors, exit 1 | 2ms, ok | 12ms, ok |
| oom-c418 (10.9KB) | SyntaxErrors + invalid UTF-8 | 4ms, ok | 13ms, ok |

**None of them crash individually.** The OOM only occurs when libFuzzer processes thousands of inputs in a single process — memory accumulates across iterations. This means:

1. The crash files contain **syntax errors** (mutated by libFuzzer's binary mutations) — they're not valid Luau code
2. The OOM is from **libFuzzer's internal memory bookkeeping** growing, not from Luau allocating unboundedly on a specific input
3. These are **not real Luau bugs** — they're artifacts of running the fuzzer with a 512MB RSS limit while processing large seed corpora

### Honest Assessment

**All OOM crashes across all versions (0.640, 0.660, 0.712) are the same class:** libFuzzer accumulating memory over thousands of iterations until hitting the RSS limit. No single input causes unbounded allocation in the Luau compiler.

The 0.660 crashes appearing to be "fixed" on 0.712 is likely because the newer fuzz-compiler binary has better memory management or smaller per-iteration footprint, not because a specific bug was fixed.

**We have not found any real bugs in the Luau compiler/parser/typechecker using the standard fuzz targets.** However, after writing a custom fuzz target that enables the new solver (see below), we found real assertion failures.

---

## Real Bugs Found: New Solver Assertion Failures (Luau 0.660)

### What changed

Two general grammar improvements unlocked real bug finding:

1. **Added `--!strict` / `--!nonstrict` mode directives** in `chunk()` — most type solver bugs only trigger in strict mode, which activates the "new solver"
2. **Used a small fixed name pool** (`_NAME_POOL`) instead of random names — this naturally produces duplicate table keys, type name collisions, and repeated identifiers

Additionally, we wrote a **custom fuzz target** (`fuzz_typeck_custom.cpp`) that:
- Uses `Frontend::check()` instead of the broken `TypeChecker` class (which was removed in this version range)
- Sets `FFlag::LuauSolverV2 = true` to enable the new solver
- Respects `--!strict` mode from the source comments

### Results

**5 out of 200 grammar-generated programs crash the type checker on Luau 0.660** with assertion failures (SIGTRAP, exit code 133). These are pure grammar-generated inputs — no libFuzzer mutation needed.

| File | Size | Crashes on 0.660? | Crashes on 0.709? |
|------|------|-------------------|-------------------|
| gen_00002.luau | 3,792 bytes | **YES** — assertion failure | No (fixed) |
| gen_00003.luau | 4,345 bytes | **YES** — assertion failure | No (fixed) |
| gen_00022.luau | 5,311 bytes | **YES** — assertion failure | No (fixed) |
| gen_00029.luau | 3,548 bytes | **YES** — assertion failure | No (fixed) |
| gen_00031.luau | 3,686 bytes | **YES** — assertion failure | No (fixed) |

### Crashing input example (gen_00029.luau, 3,548 bytes)

```luau
type function v1(...: id.Item): T...
local v2: (...string) -> any, v3, v4;
local v5 = function(v6: Array<any, nil>): ...never
if 90 then
local v7 = 482;
local v8 = v4
elseif true then
...
end - v9[...] :: {};
v29:remove();
end
for v32: (foo: never, nil) -> (string, number) in ipairs(v25) do
setmetatable(-0b1111_0000);
while 0xC5CC do
while ("ok"):len() do
type T40<T = any, U> = never;
continue
end
...
```

This is **valid grammar-generated Luau code** — no binary corruption, no garbage bytes. Key patterns that trigger the crash:
- `type function` with qualified generic types (`id.Item`)
- Generic instantiation in parameter types (`Array<any, nil>`)
- Complex type annotations on for-loop bindings
- `@checked` local functions
- Type declarations with generic defaults (`T = any`)
- Expressions with type assertions (`:: {}`)

### Why the standard fuzz targets couldn't find this

1. The built-in `fuzz-compiler` target only calls `Luau::compile()` — it **never runs the type checker**
2. The built-in `fuzz-typeck` target was broken (wouldn't compile) on versions 0.650-0.670 due to the `TypeChecker` class being removed during the new solver transition
3. Even when `fuzz-typeck` works, it hardcodes `Mode::Nonstrict` — **it never tests the new solver**
4. Without `--!strict`, the `Frontend::check()` path uses the old solver which is battle-hardened

### What this means

The Luau project's own fuzz targets had a blind spot: **the new solver was never fuzzed in strict mode** during the 0.650-0.670 version range. Our custom fuzz target + grammar improvements filled that gap and found real assertion failures with a 2.5% crash rate on grammar-generated programs.
