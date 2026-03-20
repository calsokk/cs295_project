# Targeted generator for the Luau NCG buffer constant-folding crash.
# Generates buffer ops with extreme integer offsets (INT_MAX, INT_MIN, etc.).

import sys
import os
import random

sys.path.insert(0, os.path.dirname(__file__))

from luau_grammar import LuauGenerator

EXTREME_INTS = [
    2147483647,   # INT_MAX
    -2147483648,  # INT_MIN
    2147483648,   # INT_MAX + 1
    4294967295,   # UINT_MAX
    -1,
    0,
    65535,
    65536,
    -65536,
    1073741823,   # INT_MAX / 2
]

BUFFER_OPS = [
    "buffer.readi8",
    "buffer.readu8",
    "buffer.readi16",
    "buffer.readu16",
    "buffer.readi32",
    "buffer.readu32",
    "buffer.readf32",
    "buffer.readf64",
    "buffer.writei8",
    "buffer.writeu8",
    "buffer.writei16",
    "buffer.writeu16",
    "buffer.writei32",
    "buffer.writeu32",
    "buffer.writef32",
    "buffer.writef64",
]

LuauGenerator.RULE_WEIGHTS = {
    "stat_local":           2.0,
    "stat_functioncall":    5.0,   # buffer ops are function calls
    "exp_number":           5.0,   # generate lots of numeric constants
    "exp_call":             3.0,
    "stat_type_decl":       0.1,
    "stat_while":           0.1,
    "stat_for_numeric":     0.1,
    "stat_for_generic":     0.1,
    "stat_repeat":          0.1,
    "exp_function":         0.1,
    "exp_if_else":          0.1,
}


class BufferBugGenerator(LuauGenerator):

    def _extreme_int(self):
        return str(self._pick_from(EXTREME_INTS))

    def _stat_functioncall(self):
        if self._pick_int(0, 2) == 0:
            return self._buffer_op()
        return super()._stat_functioncall()

    def _buffer_op(self):
        op = self._pick_from(BUFFER_OPS)
        buf_var = self._existing_var() if self._defined_vars else "buf"
        offset = self._extreme_int()
        if "write" in op:
            return f"{op}({buf_var}, {offset}, {self._extreme_int()})"
        return f"{op}({buf_var}, {offset})"

    def _exp_number(self):
        if self._pick_int(0, 2) == 0:
            return self._extreme_int()
        return super()._exp_number()

    def chunk(self):
        buf_var = self._fresh_var()
        size = self._pick_int(1, 64)
        return f"local {buf_var} = buffer.create({size})\n{self.block()}"


def generate_program(max_depth=5, seed=None):
    gen = BufferBugGenerator(max_depth=max_depth, seed=seed)
    return gen.chunk()


if __name__ == "__main__":
    for i in range(3):
        print(f"--- Program {i + 1} ---")
        print(generate_program(seed=i))
        print()
