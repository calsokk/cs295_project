# Analysis: Known Luau Bugs vs Our Grammar

## Goal

Figure out which known bugs our fuzzer could have found, why it didn't, and what to change.

---

## Known Bugs with Reproducers

### Bug 1: Duplicate table key assertion (#1540, #1600)

**Reproducer:**
```luau
--!strict
type dict = { read vals: {[string]: number} }
local _:dict = { vals = { key = 1, key = 1 } }
```

**What triggers it:** Duplicate key names in a table literal when the table has a string indexer type.

**Fixed in:** ~0.662 (Feb 14, 2025)

**Can our grammar generate this?** NO.
- We never generate `--!strict` mode directives
- We never generate duplicate field names in table constructors (each field gets a random `_simple_name()`)
- We never generate typed locals with table indexer types that match the field pattern

**What to add:**
1. Add `--!strict` and `--!nonstrict` mode comments at the top of programs
2. Deliberately generate duplicate keys in table constructors
3. Generate locals with type annotations that have string union indexers matching the keys

---

### Bug 2: table.freeze() with missing argument (#1498)

**Reproducer:**
```luau
table.freeze()  -- no arguments = crash
```

**What triggers it:** Calling `table.freeze()` with zero arguments.

**Can our grammar generate this?** NO.
- Our `_exp_call` fix now gives `table.freeze` exactly 1 argument (it's in `_CALLS_1ARG`)
- Before the fix, we had random 0-3 args, so the OLD grammar could have generated this accidentally

**What to add:**
1. Add a rule that specifically calls builtins with **wrong argument counts** (0 args, too many args) — this is a known bug class

---

### Bug 3: Syntax error + lambda crash (#1496)

**Reproducer:**
```luau
--!strict
type t = 'test'
type t = typeof;
(function() end)()
```

**What triggers it:** A lambda expression after a syntax error in a redefined `typeof` type. The crash happens during error recovery in the type solver.

**Can our grammar generate this?** PARTIALLY.
- We can generate `type t = typeof(...)` but not the malformed `type t = typeof;` (missing parens)
- We never generate intentionally malformed syntax
- We never redefine the same type name twice
- We generate IIFEs (`(function() end)()`) — but only via `_exp_call` calling a function expression, never this exact pattern

**What to add:**
1. Allow generating **intentionally malformed type expressions** (missing parens, truncated)
2. Reuse type names (generate `type t = ...` twice with the same name)
3. Generate IIFE patterns: `(function() end)()`

---

### Bug 4: Recursive generic type ICE (#1686)

**Reproducer:**
```luau
type a<T> = {a<{T}>}
type b<T> = {b<T | string>}
type c<T> = {c<T & string>}
type d<T> = (d<T | string>) -> ()
```

**What triggers it:** A type alias that references itself with a modified generic parameter (wrapped in table, unioned, intersected).

**Fixed in:** 0.687 (Aug 15, 2025)

**Can our grammar generate this?** NO.
- We never generate self-referencing types. Type names are `T1`-`T100` (random) and type bodies never reference the name being defined.
- We never wrap the generic parameter in the recursive reference (`{T}`, `T | string`)

**What to add:**
1. Generate **self-referencing type aliases**: `type Foo<T> = {Foo<{T}>}`
2. The key pattern is: the type body uses the type name with a *modified* generic parameter

---

### Bug 5: Typecast expression in assignment (#1501)

**Reproducer:**
```luau
--!strict
(1 :: number) =
```

**What triggers it:** Using a typecasted expression as an lvalue (left side of assignment). This is a parse error that causes a crash during error recovery.

**Can our grammar generate this?** NO.
- We never generate type assertions on the left side of assignments
- Our assignments always use `_var()` for the left side which produces `NAME`, `NAME.field`, or `NAME[exp]`

**What to add:**
1. Sometimes generate `(exp :: Type) = exp` — typecasted expression as lvalue
2. More generally: generate **invalid lvalues** (literals, function calls, etc. on the left side of `=`)

---

## Summary: Why We Found Nothing

| Bug | Key Pattern | Our Grammar Has It? |
|-----|------------|---------------------|
| #1540 | `--!strict` + duplicate table keys + indexer type | NO — no strict mode, no duplicate keys |
| #1498 | `table.freeze()` with 0 args | NO — we fixed arg counts (ironic) |
| #1496 | Syntax error + lambda after bad `typeof` type | NO — no intentional syntax errors |
| #1686 | Self-referencing recursive generic types | NO — types never reference themselves |
| #1501 | Typecast expression as assignment lvalue | NO — lvalues are always valid |

**Common theme:** These bugs are all triggered by **unusual combinations** that our grammar never produces:
1. **Mode directives** (`--!strict`) — we never emit these
2. **Duplicate/repeated identifiers** — we always generate unique names
3. **Intentionally malformed syntax** — our grammar only produces valid syntax
4. **Self-referencing types** — we never create cycles
5. **Invalid lvalue expressions** — our assignments always use proper variables

---

## Recommended Changes (prioritized)

### High priority — would have found multiple bugs:

1. **Add `--!strict` mode directive** at the top of programs. Most crashes are in the "new solver" which only runs in strict mode.

2. **Generate self-referencing type aliases**: `type T<U> = {T<{U}>}`, `type T<U> = {T<U | string>}`. This is the single most impactful change — recursive types are the #1 source of type checker crashes.

3. **Generate duplicate table keys**: Instead of always using `_simple_name()` for field names, sometimes reuse the same name.

### Medium priority — would have found 1-2 bugs:

4. **Generate calls with wrong arg counts**: Specifically, call builtins with 0 arguments sometimes. This catches the `table.freeze()` class of bugs.

5. **Generate invalid lvalues**: Sometimes put expressions like `(exp :: Type)` or `func()` on the left side of `=`.

### Lower priority — targets error recovery bugs:

6. **Reuse type names**: Generate `type t = X` then `type t = Y` in the same block.

7. **Generate intentionally malformed type expressions**: Missing parens in typeof, truncated type expressions.
