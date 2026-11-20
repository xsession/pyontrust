"""Safe expression evaluator for user-supplied formulas (FlowLab Expression).

``eval()`` with trimmed builtins is *not* a sandbox — ``().__class__.__base__
.__subclasses__()`` reaches arbitrary classes and from there the OS.  This
evaluator walks the AST instead and allows only:

* literals (numbers, strings, booleans, None), lists / tuples / dicts
* names from the supplied variables, ``math`` constants (``pi``, ``e``, …)
* arithmetic, comparisons, ``and`` / ``or`` / ``not``, ``x if c else y``
* subscripts ``x[i]`` / slices
* calls to whitelisted functions (``abs``, ``min``, ``round``, ``math.sqrt``…)

No attribute access except ``math.<name>``, no comprehensions, lambdas,
f-strings or dunder names.  Sizes are bounded to stop ``10**10**10`` style
resource exhaustion.
"""
from __future__ import annotations

import ast
import math
import operator
from typing import Any

MAX_EXPR_LEN = 500
MAX_POW_EXP = 1000
MAX_SEQ_LEN = 100_000


class ExprError(ValueError):
    """Expression rejected or failed to evaluate."""


_FUNCS: dict[str, Any] = {
    "abs": abs, "min": min, "max": max, "round": round, "len": len, "sum": sum,
    "int": int, "float": float, "str": str, "bool": bool, "list": list, "tuple": tuple,
    "sorted": sorted, "any": any, "all": all, "range": range,
}
_MATH = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}

_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.BitAnd: operator.and_, ast.BitOr: operator.or_,
    ast.BitXor: operator.xor, ast.LShift: operator.lshift, ast.RShift: operator.rshift,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_, ast.Invert: operator.invert}
_CMP = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge, ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b, ast.Is: operator.is_, ast.IsNot: operator.is_not,
}


def safe_eval(expr: str, variables: dict[str, Any] | None = None) -> Any:
    """Evaluate ``expr`` with ``variables``; raises :class:`ExprError`."""
    if not isinstance(expr, str) or len(expr) > MAX_EXPR_LEN:
        raise ExprError(f"Expression must be a string of at most {MAX_EXPR_LEN} characters")
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as exc:
        raise ExprError(f"Syntax error: {exc.msg}") from None
    env = dict(variables or {})
    try:
        return _Eval(env).visit(tree.body)
    except ExprError:
        raise
    except (ArithmeticError, TypeError, ValueError, IndexError, KeyError) as exc:
        raise ExprError(f"{type(exc).__name__}: {exc}") from None


class _Eval(ast.NodeVisitor):
    def __init__(self, env: dict[str, Any]) -> None:
        self.env = env

    def generic_visit(self, node: ast.AST) -> Any:
        raise ExprError(f"'{type(node).__name__}' is not allowed in expressions")

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id.startswith("_"):
            raise ExprError("Names starting with '_' are not allowed")
        if node.id in self.env:
            return self.env[node.id]
        if node.id in ("True", "False", "None"):
            return {"True": True, "False": False, "None": None}[node.id]
        if node.id in _MATH and not callable(_MATH[node.id]):
            return _MATH[node.id]          # pi, e, tau, inf, nan
        raise ExprError(f"Unknown name '{node.id}'")

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if isinstance(node.value, ast.Name) and node.value.id == "math" and node.attr in _MATH:
            return _MATH[node.attr]
        raise ExprError("Attribute access is not allowed (only math.<name>)")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op = _BIN.get(type(node.op))
        if op is None:
            raise ExprError("Operator not allowed")
        a, b = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Pow) and isinstance(b, (int, float)) and abs(b) > MAX_POW_EXP:
            raise ExprError("Exponent too large")
        if isinstance(node.op, ast.LShift) and isinstance(b, int) and b > 64:
            raise ExprError("Shift too large")
        if isinstance(node.op, ast.Mult):
            for seq, n in ((a, b), (b, a)):
                if isinstance(seq, (str, list, tuple)) and isinstance(n, int) and len(seq) * n > MAX_SEQ_LEN:
                    raise ExprError("Result too large")
        return op(a, b)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        return _UNARY[type(node.op)](self.visit(node.operand))

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if isinstance(node.op, ast.And):
            result: Any = True
            for v in node.values:
                result = self.visit(v)
                if not result:
                    return result
            return result
        result = False
        for v in node.values:
            result = self.visit(v)
            if result:
                return result
        return result

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for op, comp in zip(node.ops, node.comparators):
            right = self.visit(comp)
            if not _CMP[type(op)](left, right):
                return False
            left = right
        return True

    def visit_IfExp(self, node: ast.IfExp) -> Any:
        return self.visit(node.body) if self.visit(node.test) else self.visit(node.orelse)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        return self.visit(node.value)[self.visit(node.slice)]

    def visit_Slice(self, node: ast.Slice) -> Any:
        return slice(*(self.visit(p) if p is not None else None for p in (node.lower, node.upper, node.step)))

    def visit_List(self, node: ast.List) -> Any:
        return [self.visit(e) for e in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        return tuple(self.visit(e) for e in node.elts)

    def visit_Dict(self, node: ast.Dict) -> Any:
        if any(k is None for k in node.keys):
            raise ExprError("'**' unpacking is not allowed")
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values)}

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
            fn = _FUNCS[node.func.id]
        elif (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
              and node.func.value.id == "math" and callable(_MATH.get(node.func.attr))):
            fn = _MATH[node.func.attr]
        else:
            raise ExprError("Only whitelisted functions may be called (abs, min, max, round, math.*, …)")
        if any(isinstance(a, ast.Starred) for a in node.args) or any(k.arg is None for k in node.keywords):
            raise ExprError("'*' / '**' arguments are not allowed")
        args = [self.visit(a) for a in node.args]
        kwargs = {k.arg: self.visit(k.value) for k in node.keywords}
        if fn is range and any(isinstance(a, int) and abs(a) > MAX_SEQ_LEN for a in args):
            raise ExprError("range too large")
        return fn(*args, **kwargs)
