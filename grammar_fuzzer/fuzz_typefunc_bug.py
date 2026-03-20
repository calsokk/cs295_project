# Targeted generator for the Luau type function too-many-arguments crash.
# Generates user-defined type functions with large argument counts.

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from luau_grammar import LuauGenerator

LuauGenerator.RULE_WEIGHTS = {
    "stat_type_decl":       5.0,   # generate type declarations often
    "type_union":           3.0,   # unions stress the type function args
    "type_intersection":    3.0,
    "type_simple":          1.0,
    "stat_local":           0.2,   # deprioritize unrelated rules
    "stat_while":           0.1,
    "stat_for_numeric":     0.1,
    "stat_for_generic":     0.1,
    "stat_repeat":          0.1,
}


class TypeFuncGenerator(LuauGenerator):

    def _stat_type_decl(self):
        if self._pick_bool():
            return self._user_type_function()
        return super()._stat_type_decl()

    def _user_type_function(self):
        name = f"TF{self._pick_int(1, 100)}"
        num_params = self._pick_int(8, 20)
        params = ", ".join(f"t{i}" for i in range(num_params))
        defn = f"type function {name}({params})\n    return t0\nend"
        type_args = ", ".join(
            self._pick_from(self.BUILTIN_TYPES) for _ in range(num_params)
        )
        var = self._fresh_var()
        invocation = f"local {var}: {name}<{type_args}> = (nil :: any)"
        return f"{defn}\n{invocation}"

    def chunk(self):
        return "--!strict\n" + super().chunk()


def generate_program(max_depth=5, seed=None):
    gen = TypeFuncGenerator(max_depth=max_depth, seed=seed)
    return gen.chunk()


if __name__ == "__main__":
    for i in range(3):
        print(f"--- Program {i + 1} ---")
        print(generate_program(seed=i))
        print()
