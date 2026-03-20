# Finding a Type Checker Bug in Luau 0.660

## The Bug

We found an assertion failure (SIGTRAP) in Luau 0.660's new constraint-based type solver. The crash occurs when the type checker processes grammar-generated Luau programs in strict mode. Five out of 200 generated programs trigger the bug, which was fixed by version 0.709.

## How We Found It

We started with a grammar-based fuzzer that generated syntactically valid Luau programs and fed them to the built-in fuzz targets (`fuzz-compiler`, `fuzz-typeck`). After millions of iterations, we found nothing. Investigating why, we discovered two problems:

First, the built-in `fuzz-compiler` only calls `Luau::compile()`, which generates bytecode without ever running the type checker. Second, `fuzz-typeck` was broken on versions 0.650-0.670 due to a class removal during the V2 solver rewrite, and even when functional, it hardcoded `Mode::Nonstrict`, meaning it never tested the new solver.

We analyzed known bugs from the Luau issue tracker and found a pattern: nearly all crashes were in the new solver, activated only in strict mode. This led to two changes:

1. We added `--!strict` mode directives to generated programs, activating the new solver code path.
2. We wrote a custom fuzz target (`fuzz_typeck_custom.cpp`) that uses `Frontend::check()` and enables `FFlag::LuauSolverV2`.

We also replaced random identifier generation with a small fixed name pool, causing natural collisions in table keys and type names.

## The Input

The crashing input (`gen_00029.luau`, 3,548 bytes) is a pure grammar-generated Luau program combining `type function` declarations with qualified generic types (`id.Item`), generic instantiation (`Array<any, nil>`), complex function type annotations on for-loop bindings, and type assertions. These features together push the constraint solver into an unexpected state, triggering an internal assertion that aborts the process.


How it works:
 1. We run generate_corpus.py → creates 200 .luau files using our grammar (with --!strict, small name pool,     
  etc.)                                  
  2. We compile fuzz_typeck_custom.cpp + Luau's libraries into one binary called fuzz-typeck-custom. This binary 
  has libFuzzer built in.                                                                                        
  3. We run: ./fuzz-typeck-custom corpus_dir/ seeds_dir/                                                         
  4. LibFuzzer takes over:                                                                                       
    - Loads all 200 seed files                              
    - Picks one, passes its bytes to LLVMFuzzerTestOneInput()                                                    
    - Our function sets those bytes as Luau source code and calls Frontend::check() with the new solver          
    - If the type checker crashes → libFuzzer saves the input and reports it                                     
    - If it doesn't crash → libFuzzer records which code branches were hit, mutates the input (flip bits, insert 
  bytes, combine two inputs), and tries again                                                                    
    - Repeats thousands of times per second                                                                      
                                                                                                                 
  In our case, step 4 never even got to mutation — 5 of the raw seeds crashed the type checker immediately.      
  LibFuzzer loaded the seed, passed it to the type checker, and got a SIGTRAP back.    