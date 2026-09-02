from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from random import Random
from time import perf_counter
from typing import Any, ClassVar

import re2 as re
from opentelemetry import trace

from ..infrastructure.logger import get_logger

_tracer = trace.get_tracer('pox-discord-bot-tracer.dsl_evaluator')


class SafeStringPredicateEvaluator:
    _OPERATORS: ClassVar[dict[type[ast.AST], Callable]] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.In: lambda l, r: l in r,
    }
    _BINOPS: ClassVar[dict[type[ast.AST], Callable]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _LOGICAL_OP: ClassVar[dict[type[ast.AST], Callable]] = {
        ast.And: all,
        ast.Or: any,
    }
    _NODE_CONTAINERS: ClassVar[set[type[ast.AST]]] = {ast.Expression, ast.Module}
    _NODE_VALUES: ClassVar[set[type[ast.AST]]] = {
        ast.Constant,
        ast.Name,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Subscript,
        ast.Slice,
    }
    _NODE_CONTROLS: ClassVar[set[type[ast.AST]]] = {
        ast.Call,
        ast.keyword,
        ast.arguments,
        ast.arg,
        ast.IfExp,
    }
    _NODE_OPERATORS: ClassVar[set[type[ast.AST]]] = {
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.Is,
        ast.IsNot,
        ast.BoolOp,
        ast.UnaryOp,
        ast.Not,
        ast.UAdd,
        ast.USub,
        ast.Invert,
        ast.BinOp,
        ast.Add,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Div,
    }
    SAFE_BASE_NODES: ClassVar[set[type[ast.AST]]] = (
        _NODE_CONTAINERS | _NODE_VALUES | _NODE_CONTROLS | _NODE_OPERATORS
    )
    CTX_NODES: ClassVar[set[type[ast.AST]]] = {
        ast.Load,
        ast.Store,
        ast.Del,
    }
    ALLOWED_NODES: ClassVar[set[type[ast.AST]]] = SAFE_BASE_NODES | CTX_NODES
    ALLOWED_STRING_METHODS: ClassVar[set[str]] = {
        'upper',
        'lower',
        'swapcase',
        'title',
        'startswith',
        'endswith',
    }
    ALLOWED_FUNCTIONS: ClassVar[set[str]] = {
        'range',
        'rmatch',
        'leet',
        'chance',
        'swap',
        'find_char',
    }
    _SYNTAX_KEYWORDS: ClassVar[dict[str, str]] = {
        '&&': 'and',
        '||': 'or',
        'is': '==',
        'eq': '==',
        'neq': '!=',
    }
    _KEYWORD_PATTERN = re.compile(
        r'\b('
        + '|'.join(re.escape(k) for k in _SYNTAX_KEYWORDS if k.isalnum())
        + r')\b|'
        + '|'.join(re.escape(k) for k in _SYNTAX_KEYWORDS if not k.isalnum()),
    )
    MAX_RANGE = 1000
    MAX_RECURSION_DEPTH = 50

    def __init__(self, expression: str, rng: Random | None = None):
        self.logger = get_logger(__name__, prefix='PredicateDSLParser')
        self.expression = expression
        self.rng = rng or Random()
        self.error_message: str | None = None

        def _replace_match(match: re._Match) -> str:
            word = match.group(0)
            if not isinstance(word, str):
                return ''

            return self._SYNTAX_KEYWORDS.get(word, word)

        clean_expr = self._KEYWORD_PATTERN.sub(_replace_match, expression)

        with _tracer.start_as_current_span('dsl.compile') as span:
            try:
                self.node = ast.parse(clean_expr, mode='eval').body
                self._validate_ast(self.node)
                span.set_attribute('dsl.valid', True)
            except Exception as e:
                self.node = None
                self.error_message = f'Syntax Error: {e}'

                span.set_attribute('dsl.valid', False)
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

                self.logger.exception('Failed to parse and validate DSL expression')

    def evaluate(self, char: str, index: int, text: str) -> str:
        if self.node is None:
            return 'keep'

        with _tracer.start_as_current_span('dsl.evaluate') as span:
            span.set_attribute('dsl.char', char)
            span.set_attribute('dsl.index', index)
            span.set_attribute('dsl.text_length', len(text))

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
                'leet': lambda c: {
                    'a': '4',
                    'e': '3',
                    'i': '1',
                    'o': '0',
                    's': '5',
                }.get(
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

            start_time = perf_counter()
            try:
                res = self._eval_node(self.node, context, depth=0)

                if isinstance(res, bool):
                    action = 'keep' if res else 'delete'
                else:
                    action = str(res) if res is not None else 'keep'

                duration = perf_counter() - start_time
                span.set_attribute('dsl.result_action', action)
                span.set_attribute('dsl.duration_seconds', duration)
            except ValueError as ve:
                self.error_message = str(ve)
                span.record_exception(ve)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(ve)))
                self.logger.warning(
                    'DSL evaluation security block or value error',
                    exc_info=True,
                )
                return 'keep'
            except Exception as e:
                self.error_message = f'Runtime Error: {e}'
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                self.logger.exception('DSL evaluation runtime crash')
                return 'keep'
            else:
                return action

    def _eval_node(
        self,
        node: ast.AST | None,
        context: dict[str, Any],
        depth: int,
    ) -> Any:
        if depth > self.MAX_RECURSION_DEPTH:
            raise ValueError('Max recursion depth exceeded')
        if node is None:
            return None

        # node_name = type(node).__name__
        # indent = '  ' * depth
        # self.logger.debug(
        #     '%s➔ Evaluating AST Node: %s (depth=%s)',
        #     indent,
        #     node_name,
        #     depth,
        # )

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            name_id = node.id
            if name_id in context:
                return context[name_id]
            raise ValueError(f'Undefined variable or identifier: {name_id}')

        if isinstance(node, ast.IfExp):
            cond = self._eval_node(node.test, context, depth + 1)
            if cond:
                return self._eval_node(node.body, context, depth + 1)
            return self._eval_node(node.orelse, context, depth + 1)

        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, context, depth + 1)
            current_left = left

            for op, comparator in zip(node.ops, node.comparators):
                op_type = type(op)
                if op_type not in self._OPERATORS:
                    raise ValueError('Unsupported operator')

                right = self._eval_node(comparator, context, depth + 1)
                if not self._OPERATORS[op_type](current_left, right):
                    return False
                current_left = right
            return True

        if isinstance(node, (ast.List, ast.Tuple)):
            return [self._eval_node(el, context, depth + 1) for el in node.elts]

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                obj = self._eval_node(node.func.value, context, depth + 1)
                method_name = node.func.attr

                if not isinstance(obj, str):
                    raise TypeError('Attributes are only supported on strings')

                if method_name in self.ALLOWED_STRING_METHODS:
                    method = getattr(obj, method_name)
                    args = [
                        self._eval_node(arg, context, depth + 1) for arg in node.args
                    ]
                    return method(*args)
            elif isinstance(node.func, ast.Name):
                func_obj = self._eval_node(node.func, context, depth + 1)
                func_name = node.func.id
                if func_name in self.ALLOWED_FUNCTIONS and callable(
                    func_obj,
                ):
                    args = [
                        self._eval_node(arg, context, depth + 1) for arg in node.args
                    ]
                    return func_obj(*args)
            raise ValueError(f'Unsupported function or method call: {node.func}')

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                val = True
                for v in node.values:
                    val = self._eval_node(v, context, depth + 1)
                    if not val:
                        return val
                return val

            val = False
            for v in node.values:
                val = self._eval_node(v, context, depth + 1)
                if val:
                    return val
            return val

        if isinstance(node, ast.Subscript):
            value = self._eval_node(node.value, context, depth + 1)
            slc = self._eval_node(node.slice, context, depth + 1)

            if not isinstance(value, (str, list, tuple)):
                raise TypeError('Unsafe subscript target')

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
                raise ValueError('Unsupported binary operation')

            return fn(left, right)

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self._eval_node(node.operand, context, depth + 1)

        raise ValueError(f'Unsupported syntax: {type(node).__name__}')

    def _validate_ast(self, node: ast.AST) -> None:
        for child in ast.walk(node):
            if isinstance(child, tuple(self.ALLOWED_NODES)):
                continue

            if isinstance(child, (ast.cmpop, ast.boolop, ast.operator)):
                continue

            raise ValueError(f'Disallowed AST node: {type(child).__name__}')
