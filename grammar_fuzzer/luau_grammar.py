"""
Luau Grammar-Based Fuzzer

Recursive descent generator that produces syntactically valid Luau programs
from the language grammar (https://luau.org/grammar/).
"""

import random
import string


class LuauGenerator:
    # Class-level counters shared across all instances and runs.
    # Tracks how many times each named grammar rule has been chosen.
    _rule_counts: dict = {}

    KEYWORDS = [
        "and", "break", "continue", "do", "else", "elseif", "end",
        "false", "for", "function", "if", "in", "local", "nil", "not",
        "or", "repeat", "return", "then", "true", "until", "while",
        "type", "export", "typeof",
    ]

    BINOPS = ["+", "-", "*", "/", "//", "^", "%", "..",
              "<", "<=", ">", ">=", "==", "~=", "and", "or"]

    UNOPS = ["-", "not ", "#"]

    COMPOUNDOPS = ["+=", "-=", "*=", "/=", "//=", "%=", "^=", "..="]

    BUILTIN_TYPES = ["number", "string", "boolean", "nil", "any", "never"]

    def __init__(self, provider=None, max_depth=5, seed=None):
        self._provider = provider
        self._max_depth = max_depth
        self._depth = 0
        self._var_counter = 0
        self._defined_vars = []
        if seed is not None:
            random.seed(seed)


    def _pick_int(self, lo, hi):
        if self._provider and hasattr(self._provider, "ConsumeIntInRange"):
            return self._provider.ConsumeIntInRange(lo, hi)
        return random.randint(lo, hi)

    def _pick_bool(self):
        return self._pick_int(0, 1) == 1

    def _pick_from(self, choices):
        idx = self._pick_int(0, len(choices) - 1)
        return choices[idx]

    def _pick_rule(self, named_choices):
        names = [n for n, _ in named_choices]
        callables = [c for _, c in named_choices]

        if self._provider:
            idx = self._pick_int(0, len(callables) - 1)
        else:
            counts = [LuauGenerator._rule_counts.get(n, 0) for n in names]
            weights = [1.0 / (c + 1) for c in counts]
            chosen = random.choices(names, weights=weights, k=1)[0]
            idx = names.index(chosen)

        chosen_name = names[idx]
        LuauGenerator._rule_counts[chosen_name] = (
            LuauGenerator._rule_counts.get(chosen_name, 0) + 1
        )
        return callables[idx]()

    @classmethod
    def coverage_report(cls):
        # Return rule hit counts sorted from least to most covered.
        return dict(sorted(cls._rule_counts.items(), key=lambda kv: kv[1]))

    @classmethod
    def reset_coverage(cls):
        # Clear all rule counters
        cls._rule_counts.clear()

    def _pick_float(self):
        if self._provider and hasattr(self._provider, "ConsumeRegularFloat"):
            return self._provider.ConsumeRegularFloat()
        return random.uniform(-1000, 1000)

    def _fresh_var(self):
        self._var_counter += 1
        name = f"v{self._var_counter}"
        self._defined_vars.append(name)
        return name

    def _existing_var(self):
        if self._defined_vars:
            return self._pick_from(self._defined_vars)
        return self._fresh_var()

    def _name(self):
        if self._defined_vars and self._pick_int(0, 2) > 0:
            return self._existing_var()
        return self._fresh_var()

    def _simple_name(self):
        letters = "abcdefghijklmnopqrstuvwxyz"
        length = self._pick_int(1, 4)
        return "".join(self._pick_from(list(letters)) for _ in range(length))

    def _enter(self):
        self._depth += 1

    def _leave(self):
        self._depth -= 1

    def _at_max_depth(self):
        return self._depth >= self._max_depth

    def chunk(self):
        """chunk ::= block"""
        return self.block()

    def block(self):
        num_stmts = self._pick_int(1, 5) if not self._at_max_depth() else 1
        stmts = []
        for _ in range(num_stmts):
            stmts.append(self.stat())
            if self._pick_bool():
                stmts[-1] += ";"
        if self._pick_int(0, 3) == 0:
            stmts.append(self.laststat())
        return "\n".join(stmts)

    def laststat(self):
        choice = self._pick_int(0, 2)
        if choice == 0:
            if self._pick_bool():
                return "return " + self.explist()
            return "return"
        elif choice == 1:
            return "break"
        else:
            return "continue"

    # --- Statements ---

    def stat(self):
        self._enter()
        try:
            if self._at_max_depth():
                return self._stat_simple()

            choices = [
                ("stat_local",          self._stat_local),
                ("stat_assignment",     self._stat_assignment),
                ("stat_functioncall",   self._stat_functioncall),
                ("stat_do",             self._stat_do),
                ("stat_while",          self._stat_while),
                ("stat_repeat",         self._stat_repeat),
                ("stat_if",             self._stat_if),
                ("stat_for_numeric",    self._stat_for_numeric),
                ("stat_for_generic",    self._stat_for_generic),
                ("stat_function_def",   self._stat_function_def),
                ("stat_local_function", self._stat_local_function),
                ("stat_compound_assign",self._stat_compound_assign),
                ("stat_type_decl",      self._stat_type_decl),
            ]
            return self._pick_rule(choices)
        finally:
            self._leave()

    def _stat_simple(self):
        var = self._fresh_var()
        return f"local {var} = {self._terminal_exp()}"

    def _stat_local(self):
        name = self._fresh_var()
        if self._pick_bool():
            type_ann = f": {self.simple_type()}" if self._pick_bool() else ""
            return f"local {name}{type_ann} = {self.exp()}"
        return f"local {name}"

    def _stat_assignment(self):
        var = self._existing_var() if self._defined_vars else self._fresh_var()
        if not self._defined_vars:
            return f"local {var} = {self.exp()}"
        return f"{var} = {self.exp()}"

    def _stat_compound_assign(self):
        var = self._existing_var() if self._defined_vars else self._fresh_var()
        if not self._defined_vars:
            return f"local {var} = {self.exp()}"
        op = self._pick_from(self.COMPOUNDOPS)
        return f"{var} {op} {self.exp()}"

    def _stat_functioncall(self):
        func = self._pick_from(["print", "tostring", "tonumber", "type",
                                 "error", "assert", "pcall", "select"])
        return f"{func}({self.exp()})"

    def _stat_do(self):
        return f"do\n{self.block()}\nend"

    def _stat_while(self):
        return f"while {self.exp()} do\n{self.block()}\nend"

    def _stat_repeat(self):
        return f"repeat\n{self.block()}\nuntil {self.exp()}"

    def _stat_if(self):
        result = f"if {self.exp()} then\n{self.block()}\n"
        num_elseif = self._pick_int(0, 2)
        for _ in range(num_elseif):
            result += f"elseif {self.exp()} then\n{self.block()}\n"
        if self._pick_bool():
            result += f"else\n{self.block()}\n"
        result += "end"
        return result

    def _stat_for_numeric(self):
        var = self._fresh_var()
        start = self._pick_int(0, 10)
        stop = self._pick_int(1, 20)
        if self._pick_bool():
            step = self._pick_int(1, 3)
            return f"for {var} = {start}, {stop}, {step} do\n{self.block()}\nend"
        return f"for {var} = {start}, {stop} do\n{self.block()}\nend"

    def _stat_for_generic(self):
        k = self._fresh_var()
        v = self._fresh_var()
        iter_func = self._pick_from(["pairs", "ipairs"])
        tbl = self._existing_var() if self._defined_vars else "{}"
        return f"for {k}, {v} in {iter_func}({tbl}) do\n{self.block()}\nend"

    def _stat_function_def(self):
        name = self._fresh_var()
        params = self._param_list()
        ret_type = f": {self.simple_type()}" if self._pick_bool() else ""
        return f"function {name}({params}){ret_type}\n{self.block()}\nend"

    def _stat_local_function(self):
        name = self._fresh_var()
        params = self._param_list()
        ret_type = f": {self.simple_type()}" if self._pick_bool() else ""
        return f"local function {name}({params}){ret_type}\n{self.block()}\nend"

    def _stat_type_decl(self):
        export = "export " if self._pick_bool() else ""
        name = "T" + str(self._pick_int(1, 100))
        if self._pick_bool():
            return f"{export}type {name} = {self.type_expr()}"
        return f"{export}type {name}<T> = {self.type_expr()}"

    def _param_list(self):
        num_params = self._pick_int(0, 3)
        params = []
        for _ in range(num_params):
            p = self._fresh_var()
            if self._pick_bool():
                p += f": {self.simple_type()}"
            params.append(p)
        if self._pick_bool() and num_params > 0:
            params.append("...")
        return ", ".join(params)

    # --- Expressions ---

    def explist(self):
        num = self._pick_int(1, 3)
        return ", ".join(self.exp() for _ in range(num))

    def exp(self):
        self._enter()
        try:
            if self._at_max_depth():
                return self._terminal_exp()

            # Start with unop or simpleexp
            if self._pick_int(0, 4) == 0:
                unop = self._pick_from(self.UNOPS)
                result = f"{unop}{self.simpleexp()}"
            else:
                result = self.simpleexp()

            # Optionally chain binary ops
            if self._pick_int(0, 2) == 0:
                binop = self._pick_from(self.BINOPS)
                result = f"{result} {binop} {self.exp()}"

            # Optional type assertion
            if self._pick_int(0, 5) == 0:
                result = f"({result}) :: {self.simple_type()}"

            return result
        finally:
            self._leave()

    def simpleexp(self):
        if self._at_max_depth():
            return self._terminal_exp()

        choices = [
            ("exp_number",   self._exp_number),
            ("exp_string",   self._exp_string),
            ("exp_literal",  self._exp_literal),
            ("exp_var",      self._exp_var),
            ("exp_table",    self._exp_table),
            ("exp_function", self._exp_function),
            ("exp_call",     self._exp_call),
            ("exp_if_else",  self._exp_if_else),
            ("exp_paren",    self._exp_paren),
        ]
        return self._pick_rule(choices)

    def _terminal_exp(self):
        choice = self._pick_int(0, 4)
        if choice == 0:
            return str(self._pick_int(-100, 100))
        elif choice == 1:
            return f'"{self._simple_name()}"'
        elif choice == 2:
            return self._pick_from(["true", "false", "nil"])
        elif choice == 3 and self._defined_vars:
            return self._existing_var()
        else:
            return str(self._pick_int(0, 1000))

    def _exp_number(self):
        choice = self._pick_int(0, 3)
        if choice == 0:
            return str(self._pick_int(-1000, 1000))
        elif choice == 1:
            return f"{self._pick_int(0, 999)}.{self._pick_int(0, 999)}"
        elif choice == 2:
            return f"0x{self._pick_int(0, 0xFFFF):X}"
        else:
            return f"0b{self._pick_int(0, 255):08b}"

    def _exp_string(self):
        choice = self._pick_int(0, 2)
        content = self._simple_name()
        if choice == 0:
            return f'"{content}"'
        elif choice == 1:
            return f"'{content}'"
        else:
            return f"[[{content}]]"

    def _exp_literal(self):
        return self._pick_from(["nil", "true", "false"])

    def _exp_var(self):
        if self._defined_vars:
            return self._existing_var()
        return str(self._pick_int(0, 100))

    def _exp_table(self):
        if self._at_max_depth():
            return "{}"
        num_fields = self._pick_int(0, 4)
        fields = []
        for _ in range(num_fields):
            field_type = self._pick_int(0, 2)
            if field_type == 0:
                fields.append(f"{self._simple_name()} = {self.exp()}")
            elif field_type == 1:
                fields.append(f"[{self._pick_int(1, 10)}] = {self.exp()}")
            else:
                fields.append(self.exp())
        sep = self._pick_from([", ", "; "])
        return "{" + sep.join(fields) + "}"

    def _exp_function(self):
        params = self._param_list()
        ret_type = f": {self.simple_type()}" if self._pick_bool() else ""
        return f"function({params}){ret_type}\n{self.block()}\nend"

    def _exp_call(self):
        if self._defined_vars and self._pick_bool():
            func = self._existing_var()
        else:
            func = self._pick_from(["print", "tostring", "tonumber", "type",
                                     "math.abs", "math.floor", "math.sqrt",
                                     "string.len", "string.sub", "table.concat",
                                     "select", "rawget", "rawset", "rawlen"])
        num_args = self._pick_int(0, 3)
        args = ", ".join(self.exp() for _ in range(num_args))
        return f"{func}({args})"

    def _exp_if_else(self):
        result = f"if {self.exp()} then {self.exp()}"
        num_elseif = self._pick_int(0, 1)
        for _ in range(num_elseif):
            result += f" elseif {self.exp()} then {self.exp()}"
        result += f" else {self.exp()}"
        return result

    def _exp_paren(self):
        return f"({self.exp()})"

    # --- Type expressions ---

    def type_expr(self):
        self._enter()
        try:
            if self._at_max_depth():
                return self._pick_from(self.BUILTIN_TYPES)

            def _type_simple():
                return self.simple_type()

            def _type_union():
                num = self._pick_int(2, 3)
                return " | ".join(self.simple_type() for _ in range(num))

            def _type_intersection():
                num = self._pick_int(2, 3)
                return " & ".join(self.simple_type() for _ in range(num))

            return self._pick_rule([
                ("type_simple",       _type_simple),
                ("type_union",        _type_union),
                ("type_intersection", _type_intersection),
            ])
        finally:
            self._leave()

    def simple_type(self):
        if self._at_max_depth():
            return self._pick_from(self.BUILTIN_TYPES)

        def _stype_builtin():
            t = self._pick_from(self.BUILTIN_TYPES)
            if self._pick_bool():
                t += "?"
            return t

        return self._pick_rule([
            ("stype_builtin",   _stype_builtin),
            ("stype_builtin2",  _stype_builtin),   # double-weighted intentionally
            ("stype_builtin3",  _stype_builtin),   # mirrors original 3/6 probability
            ("stype_table",     self._type_table),
            ("stype_function",  self._type_function),
            ("stype_typeof",    lambda: f"typeof({self._terminal_exp()})"),
        ])

    def _type_table(self):
        self._enter()
        try:
            if self._at_max_depth():
                return "{}"
            if self._pick_bool():
                return "{" + self._pick_from(self.BUILTIN_TYPES) + "}"
            num_props = self._pick_int(0, 3)
            props = []
            for _ in range(num_props):
                props.append(f"{self._simple_name()}: {self.simple_type()}")
            return "{" + ", ".join(props) + "}"
        finally:
            self._leave()

    def _type_function(self):
        self._enter()
        try:
            num_params = self._pick_int(0, 3)
            params = ", ".join(self._pick_from(self.BUILTIN_TYPES)
                               for _ in range(num_params))
            ret = self._pick_from(self.BUILTIN_TYPES)
            return f"({params}) -> {ret}"
        finally:
            self._leave()

    # --- String interpolation ---

    def string_interp(self):
        parts = [self._simple_name()]
        num_interps = self._pick_int(1, 3)
        result = "`"
        for i in range(num_interps):
            result += f"{self._simple_name()} {{{self._terminal_exp()}}}"
        result += "`"
        return result


def generate_program(max_depth=5, seed=None):
    gen = LuauGenerator(max_depth=max_depth, seed=seed)
    return gen.chunk()


if __name__ == "__main__":
    # Quick test: generate and print a random program
    for i in range(3):
        print(f"--- Program {i + 1} ---")
        print(generate_program(max_depth=4, seed=i))
        print()
