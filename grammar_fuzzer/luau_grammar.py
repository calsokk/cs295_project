"""
Luau Grammar-Based Fuzzer

Recursive descent generator that produces syntactically valid Luau programs
from the language grammar (https://luau.org/grammar/).

Targets Luau 0.712.
"""

import random


class LuauGenerator:
    _rule_counts: dict = {}

    RULE_WEIGHTS: dict = {
        "type_union":        3.0,
    }

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

    ATTRIBUTES = ["native", "checked"]

    def __init__(self, provider=None, max_depth=5, seed=None):
        self._provider = provider
        self._max_depth = max_depth
        self._depth = 0
        self._var_counter = 0
        self._defined_vars = []
        self._in_vararg_func = False
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
            weights = [LuauGenerator.RULE_WEIGHTS.get(n, 1.0) for n in names]
            chosen = random.choices(names, weights=weights, k=1)[0]
            idx = names.index(chosen)

        chosen_name = names[idx]
        LuauGenerator._rule_counts[chosen_name] = (
            LuauGenerator._rule_counts.get(chosen_name, 0) + 1
        )
        return callables[idx]()

    @classmethod
    def coverage_report(cls):
        return dict(sorted(cls._rule_counts.items(), key=lambda kv: kv[1]))

    @classmethod
    def reset_coverage(cls):
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
        return self._pick_from(["0", '""', "true", "nil"])

    def _name(self):
        if self._defined_vars and self._pick_int(0, 2) > 0:
            return self._existing_var()
        return self._fresh_var()

    # Small fixed pool so name collisions (duplicate keys, type redefinitions) happen naturally
    _NAME_POOL = ["a", "b", "c", "x", "y", "z", "key", "val", "id", "name",
                  "foo", "bar", "baz", "ok", "err", "data", "self", "idx"]

    def _simple_name(self):
        return self._pick_from(self._NAME_POOL)

    def _enter(self):
        self._depth += 1

    def _leave(self):
        self._depth -= 1

    def _at_max_depth(self):
        return self._depth >= self._max_depth

    def _attributes(self):
        """attributes ::= {attribute}
        attribute ::= '@' NAME
        """
        if self._pick_int(0, 6) == 0:
            attr = self._pick_from(self.ATTRIBUTES)
            return f"@{attr} "
        return ""

    def _var(self):
        """var ::= NAME | prefixexp '[' exp ']' | prefixexp '.' NAME"""
        if not self._defined_vars or self._at_max_depth():
            return self._existing_var()

        choice = self._pick_int(0, 2)
        if choice == 0:
            return self._existing_var()
        elif choice == 1:
            # field access: var.name
            base = self._existing_var()
            field = self._simple_name()
            return f"{base}.{field}"
        else:
            # index access: var[exp]
            base = self._existing_var()
            idx = self._terminal_exp()
            return f"{base}[{idx}]"

    def _varlist(self, count=None):
        """varlist ::= var {',' var}"""
        if count is None:
            count = self._pick_int(1, 3)
        return ", ".join(self._var() for _ in range(count))

    # --- funcname ---

    def _funcname(self):
        """funcname ::= NAME {'.' NAME} [':' NAME]"""
        name = self._fresh_var()
        # Optionally add dotted path
        num_dots = self._pick_int(0, 2)
        for _ in range(num_dots):
            name += f".{self._simple_name()}"
        # Optionally add method colon
        if self._pick_bool():
            name += f":{self._simple_name()}"
        return name

    def chunk(self):
        """chunk ::= block"""
        mode = self._pick_from(["--!strict\n", "--!nonstrict\n", ""])
        return mode + self.block()

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
                ("stat_local_multi",    self._stat_local_multi),
                ("stat_assignment",     self._stat_assignment),
                ("stat_multi_assign",   self._stat_multi_assign),
                ("stat_functioncall",   self._stat_functioncall),
                ("stat_method_call",    self._stat_method_call),
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
                ("stat_type_function",  self._stat_type_function),
                ("stat_field_assign",   self._stat_field_assign),
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

    def _stat_local_multi(self):
        """local bindinglist ['=' explist] -- multiple variables"""
        num = self._pick_int(2, 4)
        bindings = []
        for _ in range(num):
            b = self._fresh_var()
            if self._pick_bool():
                b += f": {self.simple_type()}"
            bindings.append(b)
        if self._pick_bool():
            exps = ", ".join(self.exp() for _ in range(self._pick_int(1, num)))
            return f"local {', '.join(bindings)} = {exps}"
        return f"local {', '.join(bindings)}"

    def _stat_assignment(self):
        var = self._existing_var() if self._defined_vars else self._fresh_var()
        if not self._defined_vars:
            return f"local {var} = {self.exp()}"
        return f"{var} = {self.exp()}"

    def _stat_multi_assign(self):
        """varlist '=' explist -- multiple assignment"""
        if not self._defined_vars:
            return self._stat_local_multi()
        num = self._pick_int(2, 3)
        lhs = ", ".join(self._var() for _ in range(num))
        rhs = ", ".join(self.exp() for _ in range(self._pick_int(1, num)))
        return f"{lhs} = {rhs}"

    def _stat_field_assign(self):
        """Assignment to table field or index -- var.field = exp or var[exp] = exp"""
        if not self._defined_vars:
            return self._stat_simple()
        base = self._existing_var()
        if self._pick_bool():
            return f"{base}.{self._simple_name()} = {self.exp()}"
        else:
            return f"{base}[{self.exp()}] = {self.exp()}"

    def _stat_compound_assign(self):
        """var compoundop exp -- includes complex lvalues"""
        if not self._defined_vars:
            var = self._fresh_var()
            return f"local {var} = {self.exp()}"
        op = self._pick_from(self.COMPOUNDOPS)
        lhs = self._var()
        return f"{lhs} {op} {self.exp()}"

    def _stat_functioncall(self):
        func = self._pick_from(["print", "tostring", "tonumber", "type",
                                 "error", "assert", "pcall", "select",
                                 "setmetatable", "getmetatable",
                                 "rawequal", "rawget", "rawset", "rawlen",
                                 "require", "unpack", "table.insert",
                                 "table.remove", "table.sort", "table.freeze",
                                 "table.isfrozen", "table.clone",
                                 "string.format", "string.rep",
                                 "math.max", "math.min",
                                 "coroutine.wrap", "coroutine.yield",
                                 "bit32.band", "bit32.bor", "bit32.bxor",
                                 "buffer.create"])
        num_args = self._pick_int(1, 3)
        args = ", ".join(self.exp() for _ in range(num_args))
        return f"{func}({args})"

    def _stat_method_call(self):
        """prefixexp ':' NAME funcargs -- method call"""
        if not self._defined_vars:
            return self._stat_functioncall()
        obj = self._existing_var()
        method = self._pick_from(["new", "clone", "find", "sub", "len",
                                   "format", "lower", "upper", "rep",
                                   "insert", "remove", "sort", "concat",
                                   "freeze", "move"])
        num_args = self._pick_int(0, 2)
        args = ", ".join(self.exp() for _ in range(num_args))
        return f"{obj}:{method}({args})"

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
        """for bindinglist in explist do block end"""
        num_bindings = self._pick_int(1, 3)
        bindings = []
        for _ in range(num_bindings):
            b = self._fresh_var()
            if self._pick_bool():
                b += f": {self.simple_type()}"
            bindings.append(b)

        # Iterator expression
        choice = self._pick_int(0, 3)
        if choice == 0:
            iter_func = self._pick_from(["pairs", "ipairs"])
            tbl = self._existing_var() if self._defined_vars else "{}"
            iter_expr = f"{iter_func}({tbl})"
        elif choice == 1:
            # next-based iteration
            tbl = self._existing_var() if self._defined_vars else "{}"
            iter_expr = f"next, {tbl}"
        elif choice == 2:
            # Custom iterator (user-defined var or function)
            if self._defined_vars:
                iter_expr = self._existing_var()
            else:
                iter_expr = "pairs({})"
        else:
            # String iteration
            iter_expr = f'string.gmatch({self.exp()}, ".")'

        return f"for {', '.join(bindings)} in {iter_expr} do\n{self.block()}\nend"

    def _stat_function_def(self):
        """attributes 'function' funcname funcbody"""
        attrs = self._attributes()
        name = self._funcname()
        generic = self._generic_type_list_decl() if self._pick_bool() else ""
        params = self._param_list()
        ret_type = f": {self._return_type()}" if self._pick_bool() else ""
        return f"{attrs}function {name}{generic}({params}){ret_type}\n{self.block()}\nend"

    def _stat_local_function(self):
        """attributes 'local' 'function' NAME funcbody"""
        attrs = self._attributes()
        name = self._fresh_var()
        generic = self._generic_type_list_decl() if self._pick_bool() else ""
        params = self._param_list()
        ret_type = f": {self._return_type()}" if self._pick_bool() else ""
        return f"{attrs}local function {name}{generic}({params}){ret_type}\n{self.block()}\nend"

    def _stat_type_decl(self):
        """['export'] 'type' NAME ['<' GenericTypeListWithDefaults '>'] '=' Type"""
        export = "export " if self._pick_bool() else ""
        name = "T" + str(self._pick_int(1, 100))
        generics = ""
        if self._pick_bool():
            generics = self._generic_type_list_with_defaults()
        return f"{export}type {name}{generics} = {self.type_expr()}"

    def _stat_type_function(self):
        """['export'] 'type' 'function' NAME funcbody"""
        export = "export " if self._pick_bool() else ""
        name = self._fresh_var()
        generic = self._generic_type_list_decl() if self._pick_bool() else ""
        params = self._param_list()
        ret_type = f": {self._return_type()}" if self._pick_bool() else ""
        return f"{export}type function {name}{generic}({params}){ret_type}\n{self.block()}\nend"

    def _param_list(self):
        """parlist ::= bindinglist [',' '...' [':' Type]] | '...' [':' Type]"""
        # Varargs-only param list
        if self._pick_int(0, 5) == 0:
            self._in_vararg_func = True
            typed = f": {self.simple_type()}" if self._pick_bool() else ""
            return f"...{typed}"

        num_params = self._pick_int(0, 3)
        params = []
        for _ in range(num_params):
            p = self._fresh_var()
            if self._pick_bool():
                p += f": {self.simple_type()}"
            params.append(p)
        if self._pick_bool():
            self._in_vararg_func = True
            typed = f": {self.simple_type()}" if self._pick_bool() else ""
            params.append(f"...{typed}")
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

            # Optional type assertion (asexp ::= simpleexp ['::' Type])
            if self._pick_int(0, 5) == 0:
                result = f"{result} :: {self.simple_type()}"

            return result
        finally:
            self._leave()

    def simpleexp(self):
        if self._at_max_depth():
            return self._terminal_exp()

        choices = [
            ("exp_number",       self._exp_number),
            ("exp_string",       self._exp_string),
            ("exp_literal",      self._exp_literal),
            ("exp_var",          self._exp_var),
            ("exp_field_access", self._exp_field_access),
            ("exp_index_access", self._exp_index_access),
            ("exp_table",        self._exp_table),
            ("exp_function",     self._exp_function),
            ("exp_call",         self._exp_call),
            ("exp_method_call",  self._exp_method_call),
            ("exp_if_else",      self._exp_if_else),
            ("exp_paren",        self._exp_paren),
            ("exp_string_interp",self._exp_string_interp),
            ("exp_varargs",      self._exp_varargs),
            ("exp_call_string",  self._exp_call_string),
            ("exp_call_table",   self._exp_call_table),
        ]
        return self._pick_rule(choices)

    def _terminal_exp(self):
        choice = self._pick_int(0, 5)
        if choice == 0:
            return str(self._pick_int(-100, 100))
        elif choice == 1:
            return f'"{self._simple_name()}"'
        elif choice == 2:
            return self._pick_from(["true", "false", "nil"])
        elif choice == 3 and self._defined_vars:
            return self._existing_var()
        elif choice == 4 and self._in_vararg_func:
            return "..."
        else:
            return str(self._pick_int(0, 1000))

    def _exp_number(self):
        choice = self._pick_int(0, 6)
        if choice == 0:
            return str(self._pick_int(-1000, 1000))
        elif choice == 1:
            return f"{self._pick_int(0, 999)}.{self._pick_int(0, 999)}"
        elif choice == 2:
            return f"0x{self._pick_int(0, 0xFFFF):X}"
        elif choice == 3:
            return f"0b{self._pick_int(0, 255):08b}"
        elif choice == 4:
            # Scientific notation
            mantissa = self._pick_int(1, 99)
            exponent = self._pick_int(-10, 10)
            return f"{mantissa}e{exponent}"
        elif choice == 5:
            # Large/edge-case number literals (no expressions like 0/0)
            return self._pick_from([
                "0xFFFFFFFFFFFFFFFF",  # u64 overflow
                "1e308",               # near f64 max
                "1e-308",              # near f64 min positive
                "math.huge",           # inf (as a value, not expression)
                "0x7FFFFFFF",          # i32 max
                "0x80000000",          # i32 min unsigned
                "9999999999999999999", # large integer literal
            ])
        else:
            # Underscored number literals
            return self._pick_from([
                "1_000_000",
                "0xFF_FF",
                "0b1111_0000",
                "1_234.567_89",
            ])

    def _exp_string(self):
        choice = self._pick_int(0, 3)
        content = self._simple_name()
        if choice == 0:
            return f'"{content}"'
        elif choice == 1:
            return f"'{content}'"
        elif choice == 2:
            return f"[[{content}]]"
        else:
            # Multi-level long strings
            level = self._pick_int(0, 2)
            eq = "=" * level
            return f"[{eq}[{content}]{eq}]"

    def _exp_literal(self):
        return self._pick_from(["nil", "true", "false"])

    def _exp_var(self):
        if self._defined_vars:
            return self._existing_var()
        return str(self._pick_int(0, 100))

    def _exp_field_access(self):
        """prefixexp '.' NAME"""
        if self._defined_vars:
            base = self._existing_var()
            field = self._simple_name()
            return f"{base}.{field}"
        return self._terminal_exp()

    def _exp_index_access(self):
        """prefixexp '[' exp ']'"""
        if self._defined_vars:
            base = self._existing_var()
            return f"{base}[{self.exp()}]"
        return self._terminal_exp()

    def _exp_table(self):
        if self._at_max_depth():
            return "{}"
        num_fields = self._pick_int(0, 4)
        fields = []
        for _ in range(num_fields):
            field_type = self._pick_int(0, 2)
            if field_type == 0:
                # Named field with simple value
                fields.append(f"{self._simple_name()} = {self._terminal_exp()}")
            elif field_type == 1:
                # Integer index with simple value
                fields.append(f"[{self._pick_int(1, 10)}] = {self._terminal_exp()}")
            else:
                # Positional value
                fields.append(self._terminal_exp())
        sep = self._pick_from([", ", "; "])
        return "{" + sep.join(fields) + "}"

    def _exp_function(self):
        """attributes 'function' funcbody"""
        attrs = self._attributes()
        generic = self._generic_type_list_decl() if self._pick_bool() else ""
        old_vararg = self._in_vararg_func
        self._in_vararg_func = False
        params = self._param_list()
        ret_type = f": {self._return_type()}" if self._pick_bool() else ""
        body = self.block()
        self._in_vararg_func = old_vararg
        return f"{attrs}function{generic}({params}){ret_type}\n{body}\nend"

    # Builtins grouped by expected arg count for valid calls
    _CALLS_1ARG = ["print", "tostring", "tonumber", "type", "typeof",
                   "math.abs", "math.floor", "math.sqrt", "math.ceil",
                   "string.len", "string.lower", "string.upper", "string.reverse",
                   "table.freeze", "table.clone", "table.unpack",
                   "error", "getmetatable", "coroutine.create", "coroutine.wrap",
                   "bit32.bnot", "pairs", "ipairs", "rawlen"]
    _CALLS_2ARG = ["math.max", "math.min", "math.log",
                   "rawget", "string.rep", "string.find",
                   "bit32.band", "bit32.bor", "bit32.bxor",
                   "bit32.lshift", "bit32.rshift",
                   "setmetatable", "rawequal", "table.create",
                   "buffer.create", "select"]
    _CALLS_VAR = ["print", "string.format", "table.concat", "table.pack",
                  "pcall", "xpcall", "string.char", "table.insert"]

    def _exp_call(self):
        if self._defined_vars and self._pick_bool():
            func = self._existing_var()
            num_args = self._pick_int(1, 3)
            args = ", ".join(self.exp() for _ in range(num_args))
            return f"{func}({args})"

        # Pick a builtin with the right number of args
        choice = self._pick_int(0, 2)
        if choice == 0:
            func = self._pick_from(self._CALLS_1ARG)
            return f"{func}({self.exp()})"
        elif choice == 1:
            func = self._pick_from(self._CALLS_2ARG)
            return f"{func}({self.exp()}, {self.exp()})"
        else:
            func = self._pick_from(self._CALLS_VAR)
            num_args = self._pick_int(1, 4)
            args = ", ".join(self.exp() for _ in range(num_args))
            return f"{func}({args})"

    def _exp_method_call(self):
        """prefixexp ':' NAME funcargs"""
        # Use a string literal as base so method calls are valid
        content = self._simple_name()
        obj = f'("{content}")'
        # String methods with correct arg counts
        choice = self._pick_int(0, 5)
        if choice == 0:
            return f"{obj}:len()"
        elif choice == 1:
            return f"{obj}:lower()"
        elif choice == 2:
            return f"{obj}:upper()"
        elif choice == 3:
            return f"{obj}:reverse()"
        elif choice == 4:
            return f"{obj}:rep({self._pick_int(1, 5)})"
        else:
            return f"{obj}:sub({self._pick_int(1, 3)}, {self._pick_int(3, 10)})"

    def _exp_call_string(self):
        """funcargs ::= STRING -- shorthand f"str" """
        func = self._pick_from(["print", "tostring", "type", "error", "require"])
        content = self._simple_name()
        return f'{func}"{content}"'

    def _exp_call_table(self):
        """funcargs ::= tableconstructor -- shorthand f{...}"""
        func = self._pick_from(["print", "setmetatable", "unpack",
                                 "table.pack", "table.concat"])
        if self._at_max_depth():
            return f"{func}{{}}"
        num_fields = self._pick_int(0, 2)
        fields = []
        for _ in range(num_fields):
            fields.append(self.exp())
        return f"{func}{{{', '.join(fields)}}}"

    def _exp_if_else(self):
        result = f"if {self.exp()} then {self.exp()}"
        num_elseif = self._pick_int(0, 1)
        for _ in range(num_elseif):
            result += f" elseif {self.exp()} then {self.exp()}"
        result += f" else {self.exp()}"
        return result

    def _exp_paren(self):
        return f"({self.exp()})"

    def _exp_varargs(self):
        """'...' as an expression (only valid inside vararg functions)"""
        if self._in_vararg_func:
            return "..."
        # Fallback to a safe terminal if not in vararg context
        return self._terminal_exp()

    def _exp_string_interp(self):
        """stringinterp ::= INTERP_BEGIN exp { INTERP_MID exp } INTERP_END"""
        return self.string_interp()

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

        def _stype_singleton():
            """SingletonType ::= STRING | 'true' | 'false'"""
            if self._pick_bool():
                return f'"{self._simple_name()}"'
            return self._pick_from(["true", "false"])

        def _stype_qualified():
            """NAME '.' NAME ['<' TypeParams '>']"""
            module = self._simple_name()
            name = self._pick_from(["Type", "Result", "Error", "Value",
                                     "Key", "Item", "Node", "Entry"])
            if self._pick_bool():
                return f"{module}.{name}<{self._type_params()}>"
            return f"{module}.{name}"

        def _stype_generic_inst():
            """NAME '<' TypeParams '>'"""
            name = self._pick_from(["Array", "Map", "Set", "Promise",
                                     "Optional", "Result", "Ref"])
            return f"{name}<{self._type_params()}>"

        def _stype_paren():
            """'(' Type ')'"""
            return f"({self.type_expr()})"

        return self._pick_rule([
            ("stype_builtin",      _stype_builtin),
            ("stype_builtin2",     _stype_builtin),
            ("stype_singleton",    _stype_singleton),
            ("stype_qualified",    _stype_qualified),
            ("stype_generic_inst", _stype_generic_inst),
            ("stype_table",        self._type_table),
            ("stype_function",     self._type_function),
            ("stype_typeof",       lambda: f"typeof({self._terminal_exp()})"),
            ("stype_paren",        _stype_paren),
        ])

    def _type_table(self):
        """TableType ::= '{' Type '}' | '{' [PropList] '}'"""
        self._enter()
        try:
            if self._at_max_depth():
                return "{}"

            choice = self._pick_int(0, 3)
            if choice == 0:
                # Array shorthand
                return "{" + self._pick_from(self.BUILTIN_TYPES) + "}"
            elif choice == 1:
                # Named properties with optional read/write
                num_props = self._pick_int(0, 3)
                props = []
                for _ in range(num_props):
                    rw = self._pick_from(["", "read ", "write "])
                    props.append(f"{rw}{self._simple_name()}: {self.simple_type()}")
                return "{" + ", ".join(props) + "}"
            elif choice == 2:
                # Table indexer: { [KeyType]: ValueType }
                rw = self._pick_from(["", "read ", "write "])
                key_type = self._pick_from(self.BUILTIN_TYPES)
                val_type = self.simple_type()
                return f"{{{rw}[{key_type}]: {val_type}}}"
            else:
                # Mixed: indexer + properties
                rw = self._pick_from(["", "read ", "write "])
                key_type = self._pick_from(self.BUILTIN_TYPES)
                val_type = self.simple_type()
                indexer = f"{rw}[{key_type}]: {val_type}"
                props = []
                for _ in range(self._pick_int(1, 2)):
                    rw2 = self._pick_from(["", "read ", "write "])
                    props.append(f"{rw2}{self._simple_name()}: {self.simple_type()}")
                return "{" + indexer + ", " + ", ".join(props) + "}"
        finally:
            self._leave()

    def _type_function(self):
        """FunctionType ::= ['<' GenericTypeList '>'] '(' [BoundTypeList] ')' '->' ReturnType"""
        self._enter()
        try:
            generic = ""
            if self._pick_int(0, 3) == 0:
                generic = self._generic_type_list_decl()

            num_params = self._pick_int(0, 3)
            params = []
            for _ in range(num_params):
                if self._pick_bool():
                    # Named parameter: name: Type
                    params.append(f"{self._simple_name()}: {self._pick_from(self.BUILTIN_TYPES)}")
                else:
                    params.append(self._pick_from(self.BUILTIN_TYPES))
            # Optional variadic at end
            if self._pick_int(0, 4) == 0:
                params.append(f"...{self._pick_from(self.BUILTIN_TYPES)}")

            ret = self._return_type()
            return f"{generic}({', '.join(params)}) -> {ret}"
        finally:
            self._leave()

    def _return_type(self):
        """ReturnType ::= Type | TypePack | GenericTypePack | VariadicTypePack"""
        choice = self._pick_int(0, 3)
        if choice == 0:
            return self._pick_from(self.BUILTIN_TYPES)
        elif choice == 1:
            # TypePack: (Type, Type, ...)
            num = self._pick_int(1, 3)
            types = ", ".join(self._pick_from(self.BUILTIN_TYPES) for _ in range(num))
            return f"({types})"
        elif choice == 2:
            # VariadicTypePack: ...Type
            return f"...{self._pick_from(self.BUILTIN_TYPES)}"
        else:
            # GenericTypePack: T...
            return "T..."

    def _generic_type_list_decl(self):
        """<T> or <T, U> or <T, U...> for function/type declarations"""
        num = self._pick_int(1, 3)
        params = []
        for i in range(num):
            name = chr(ord('T') + i)
            if i == num - 1 and self._pick_bool():
                params.append(f"{name}...")  # type pack parameter
            else:
                params.append(name)
        return f"<{', '.join(params)}>"

    def _generic_type_list_with_defaults(self):
        """<T = number, U = string> or <T, U...> for type declarations"""
        num = self._pick_int(1, 3)
        params = []
        for i in range(num):
            name = chr(ord('T') + i)
            if i == num - 1 and self._pick_bool():
                params.append(f"{name}...")
            elif self._pick_bool():
                params.append(f"{name} = {self._pick_from(self.BUILTIN_TYPES)}")
            else:
                params.append(name)
        return f"<{', '.join(params)}>"

    def _type_params(self):
        """TypeParams ::= (Type | TypePack) [',' TypeParams]"""
        num = self._pick_int(1, 3)
        params = []
        for _ in range(num):
            if self._pick_int(0, 3) == 0 and not self._at_max_depth():
                # TypePack
                inner_num = self._pick_int(1, 2)
                inner = ", ".join(self._pick_from(self.BUILTIN_TYPES) for _ in range(inner_num))
                params.append(f"({inner})")
            else:
                params.append(self._pick_from(self.BUILTIN_TYPES))
        return ", ".join(params)

    # --- String interpolation ---

    def string_interp(self):
        """stringinterp ::= INTERP_BEGIN exp { INTERP_MID exp } INTERP_END"""
        num_interps = self._pick_int(1, 3)
        result = "`"
        for _ in range(num_interps):
            result += f"{self._simple_name()}{{{self.exp()}}}"
        result += f"{self._simple_name()}`"
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
