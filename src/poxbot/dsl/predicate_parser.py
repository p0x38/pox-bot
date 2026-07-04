from __future__ import annotations

import ast
import operator
from random import Random
from typing import Any

import re2 as re


class SafeStringPredicateEvaluator:
    _OPERATORS = {  # noqa: RUF012
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: lambda l, r: l in r,
    }
    _BINOPS = {  # noqa: RUF012
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _LOGICAL_OPS = {  # noqa: RUF012
        ast.And: all,
        ast.Or: any,
    }
    CTX_NODES = {  # noqa: RUF012
        ast.Load,
        ast.Store,
        ast.Del,
    }
    SAFE_BASE_NODES = {  # noqa: RUF012
        ast.Expression,
        ast.Module,
        
        ast.BoolOp,
        ast.BinOp,
        ast.UnaryOp,
        ast.Compare,
        ast.IfExp,
        
        ast.Constant,
        ast.Name,
        
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Subscript,
        ast.Slice,
        
        ast.Call,
        ast.keyword,
        
        ast.arguments,
        ast.arg,
        
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.Is,
        ast.IsNot,
        
        ast.Not,
        ast.UAdd,
        ast.USub,
        ast.Invert,
        
        ast.Add,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
    }
    ALLOWED_NODES = SAFE_BASE_NODES | CTX_NODES
    ALLOWED_STRING_METHODS = {  # noqa: RUF012
        'upper',
        'lower',
        'swapcase',
        'title',
        'startswith',
        'endswith',
    }
    ALLOWED_FUNCTIONS = {  # noqa: RUF012
        'range',
        'rmatch',
        'leet',
        'chance',
        'swap',
        'find_char',
    }
    MAX_RANGE = 1000
    MAX_RECURSION_DEPTH = 50

    def __init__(self, expression: str, rng: Random | None = None):
        self.rng = rng or Random()  # noqa: S311
        self.error_message: str | None = None

        clean_expr = expression.replace('&&', 'and').replace('||', 'or')
        try:
            self.node = ast.parse(clean_expr, mode='eval').body
        except Exception as e:
            self.node = None
            self.error_message = f'Syntax Error: {e}'

    def evaluate(self, char: str, index: int, text: str) -> str:
        if self.node is None:
            return 'keep'

        current_word_idx = 0
        if not char.isspace():
            last_space = text[:index].rfind(' ')
            current_word_idx = index - (last_space + 1)

        context = {
            'char': char,
            'index': index,
            'idx': index,
            'prev_char': text[index - 1] if index > 0 else '',
            'next_char': text[index + 1] if index < len(text) - 1 else '',
            'text_before': text[:index],
            'text_after': text[index + 1 :],
            'rmatch': lambda pattern: bool(re.match(pattern, char)),
            'leet': lambda c: {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5'}.get(
                c.lower(),
                c,
            ),
            'chance': lambda p: self.rng.random() < p,
            'rev_idx': len(text) - 1 - index,
            'swap': lambda c: c.swapcase(),
            'code': ord(char),
            'total_len': len(text),
            'find_char': text.find,
            'word_idx': current_word_idx,
            'range': lambda *args: list(range(*args))[: self.MAX_RANGE],
            'is_alpha': char.isalpha(),
            'is_digit': char.isdigit(),
            'is_vowel': char.lower() in 'aeiou',
            'is_space': char.isspace(),
            'upper': 'upper',
            'lower': 'lower',
            'delete': 'delete',
            'reverse': 'reverse',
            'keep': 'keep',
        }
        
        try:
            self._validate_ast(self.node)
            res = self._eval_node(self.node, context, depth=0)
            
            if isinstance(res, bool):
                return 'keep' if res else 'delete'
            
            return str(res) if res is not None else 'keep'
        except ValueError as ve:
            self.error_message = str(ve)
            return 'keep'
        except Exception as e:
            self.error_message = f'Runtime Error: {e}'
            return 'keep'

    def _eval_node(
        self,
        node: ast.AST | None,
        context: dict[str, Any],
        depth: int,
    ) -> Any:
        if depth > self.MAX_RECURSION_DEPTH:
            raise ValueError('Max recursion dept exceeded')  # noqa: TRY003

        if node is None:
            return None

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            name_id = node.id
            if name_id in context:
                val = context[name_id]
                return val() if callable(val) else val
            return name_id

        if isinstance(node, ast.IfExp):
            cond = self._eval_node(node.test, context, depth + 1)
            if cond:
                return self._eval_node(node.body, context, depth + 1)
            return self._eval_node(node.orelse, context, depth + 1)

        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context, depth + 1)

            result = True
            current_left = left

            for op, comparator in zip(node.ops, node.comparators):  # noqa: B905
                op_type = type(op)
                if op_type not in self._OPERATORS:
                    raise ValueError('Unsupported operator')  # noqa: TRY003

                right = self._eval_node(comparator, context, depth + 1)
                if not self._OPERATORS[op_type](current_left, right):
                    return False
                current_left = right
            return result

        if isinstance(node, (ast.List, ast.Tuple)):
            return [self._eval_node(el, context, depth + 1) for el in node.elts]

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                obj = self._eval_node(node.func.value, context, depth + 1)
                method_name = node.func.attr

                if not isinstance(obj, str):
                    raise TypeError('Attributes are only supported on strings')  # noqa: TRY003

                if method_name in self.ALLOWED_STRING_METHODS:
                    method = getattr(obj, method_name)
                    args = [
                        self._eval_node(arg, context, depth + 1) for arg in node.args
                    ]
                    return method(*args)
            elif isinstance(node.func, ast.Name):
                func_obj = context.get(node.func.id)
                func_name = node.func.id
                if func_name in self.ALLOWED_FUNCTIONS and callable(
                    func_obj,
                ):
                    args = [
                        self._eval_node(arg, context, depth + 1) for arg in node.args
                    ]
                    return func_obj(*args)
            raise ValueError(f'Unsupported function or method call: {node.func}')  # noqa: TRY003

        if isinstance(node, ast.BoolOp):
            values = [self._eval_node(v, context, depth + 1) for v in node.values]

            return all(values) if isinstance(node.op, ast.And) else any(values)

        if isinstance(node, ast.Subscript):
            value = self._eval_node(node.value, context, depth + 1)
            slc = self._eval_node(node.slice, context, depth + 1)

            if not isinstance(value, (str, list, tuple)):
                raise TypeError('Unsafe subscript target')  # noqa: TRY003

            return value[slc]

        if isinstance(node, ast.Slice):
            lower = self._eval_node(node.lower, context, depth + 1)
            upper = self._eval_node(node.upper, context, depth + 1)
            step = self._eval_node(node.step, context, depth + 1)
            return slice(lower, upper, step)

        if isinstance(node, ast.Dict):
            keys = [self._eval_node(k, context, depth + 1) for k in node.keys]
            values = [self._eval_node(v, context, depth + 1) for v in node.values]
            return dict(zip(keys, values, strict=True))

        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, context, depth + 1)
            right = self._eval_node(node.right, context, depth + 1)
            op_type = type(node.op)
            
            fn = self._BINOPS.get(op_type)
            if fn is None:
                raise ValueError('Unsupported binary operation')  # noqa: TRY003
            
            return fn(left, right)

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self._eval_node(node.operand, context, depth + 1)

        raise ValueError(f'Unsupported syntax: {type(node).__name__}')  # noqa: TRY003

    def _validate_ast(self, node: ast.AST) -> None:
        for child in ast.walk(node):
            if isinstance(child, tuple(self.ALLOWED_NODES)):
                continue
            
            if isinstance(child, (ast.cmpop, ast.boolop, ast.operator)):
                continue
            
            raise ValueError(f'Disallowed AST node: {type(child).__name__}')  # noqa: TRY003
