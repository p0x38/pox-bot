#!/usr/bin/env python3
# ruff: file-ignore[print]
from __future__ import annotations

import ast
import contextlib
import importlib
import inspect
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_terminal_width() -> int:
    """Get the current terminal width safely, defaulting to 100."""
    return shutil.get_terminal_size((100, 20)).columns


def analyze_transform_code(file_path: Path) -> tuple[list[str], list[str]]:
    """Deeply parse the transform() method source code via AST.

    Returns:
        tuple: (list_of_detected_kwargs_keys, list_of_raised_exceptions)
    """
    kwargs_keys: set[str] = set()
    exceptions: set[str] = set()

    with contextlib.suppress(Exception):
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'transform':
                for sub_node in ast.walk(node):
                    if isinstance(sub_node, ast.Raise):
                        if isinstance(sub_node.exc, ast.Call) and isinstance(
                            sub_node.exc.func, ast.Name
                        ):
                            exceptions.add(sub_node.exc.func.id)
                        elif isinstance(sub_node.exc, ast.Name):
                            exceptions.add(sub_node.exc.id)

                    if (
                        isinstance(sub_node, ast.Call)
                        and isinstance(sub_node.func, ast.Attribute)
                        and (
                            sub_node.func.attr == 'get'
                            and isinstance(sub_node.func.value, ast.Name)
                            and sub_node.func.value.id == 'kwargs'
                        )
                        and sub_node.args
                        and isinstance(sub_node.args[0], ast.Constant)
                    ):
                        kwargs_keys.add(str(sub_node.args[0].value))

                    if (
                        isinstance(sub_node, ast.Subscript)
                        and isinstance(sub_node.value, ast.Name)
                        and sub_node.value.id == 'kwargs'
                    ) and isinstance(sub_node.slice, ast.Constant):
                        kwargs_keys.add(str(sub_node.slice.value))

    return sorted(kwargs_keys), sorted(exceptions)


def run_inspection() -> None:
    transformers_dir = PROJECT_ROOT / 'src' / 'text_transformers' / 'transformers'

    if not transformers_dir.exists():
        print(f'Error: Directory not found -> {transformers_dir} D:<')
        sys.path.pop(0)
        return

    target_params = {
        'shift',
        'key',
        'block_size',
        'chunk_size',
        'seed_key',
        'rate',
        'key_matrix',
    }
    py_files = sorted(transformers_dir.glob('*.py'))

    table_rows: list[tuple[str, str, str, str, bool, str]] = []

    start_time = time.perf_counter()

    for file_path in py_files:
        if file_path.name.startswith('_'):
            continue

        hidden_kwargs, raised_exceptions = analyze_transform_code(file_path)
        exceptions_str = ', '.join(raised_exceptions) if raised_exceptions else 'None'

        module_name = f'src.text_transformers.transformers.{file_path.stem}'
        try:
            module = importlib.import_module(module_name)
        except Exception:  # ruff: ignore[try-except-continue]
            continue

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                inspect.isclass(attr)
                and 'Transformer' in attr_name
                and attr.__module__ == module_name
            ):
                if not hasattr(attr, 'transform'):
                    continue

                try:
                    sig = inspect.signature(attr.transform)
                    params = sig.parameters
                except Exception:  # ruff: ignore[try-except-continue]
                    continue

                found_any_param = False
                for p_name, p_info in params.items():
                    if p_name in ('self', 'text'):
                        continue
                    if p_info.kind == inspect.Parameter.VAR_KEYWORD:
                        continue

                    default_val = (
                        'Required'
                        if p_info.default is inspect.Parameter.empty
                        else str(p_info.default)
                    )
                    type_str = (
                        str(p_info.annotation)
                        .replace('typing.', '')
                        .replace("<class '", '')
                        .replace("'>", '')
                    )
                    is_target = p_name in target_params

                    table_rows.append((
                        attr_name,
                        p_name,
                        type_str,
                        default_val,
                        is_target,
                        exceptions_str,
                    ))
                    found_any_param = True

                for hidden_key in hidden_kwargs:
                    if not any(
                        row[0] == attr_name and row[1] == hidden_key
                        for row in table_rows
                    ):
                        is_target = hidden_key in target_params
                        table_rows.append((
                            attr_name,
                            f'{hidden_key} (via get)',
                            'Any (Dynamic)',
                            'Dynamic',
                            is_target,
                            exceptions_str,
                        ))
                        found_any_param = True

                if not found_any_param:
                    table_rows.append((
                        attr_name,
                        'None',
                        'None',
                        'None',
                        False,
                        exceptions_str,
                    ))

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    width = get_terminal_width()

    print('=' * width)
    print('ULTIMATE AST KWARGS & EXCEPTIONS ANALYZER REPORT'.center(width))
    print('=' * width)
    print(f'\nCompleted deep analysis in {elapsed_ms:.2f}ms!\n')

    col_class_w = max(len(row[0]) for row in table_rows) if table_rows else 20
    col_param_w = max(len(row[1]) + 2 for row in table_rows) if table_rows else 16
    col_type_w = max(len(row[2]) for row in table_rows) if table_rows else 12
    col_def_w = max(len(row[3]) for row in table_rows) if table_rows else 10

    col_class_w = max(col_class_w, 5)
    col_param_w = max(col_param_w, 5)
    col_type_w = max(col_type_w, 4)
    col_def_w = max(col_def_w, 7)

    header_left = (
        f'{"CLASS":<{col_class_w}} | '
        f'{"PARAM":<{col_param_w}} | '
        f'{"TYPE":<{col_type_w}} | '
        f'{"DEFAULT":<{col_def_w}} | '
    )

    raises_header_w = max(width - len(header_left), 10)
    print(f'{header_left}{"RAISES (AST ANALYZED)":<{raises_header_w}}')
    print('-' * width)

    for class_name, param_name, type_name, def_name, is_target, exec_str in table_rows:
        p_display = f'{param_name} *' if is_target else param_name

        line_left = (
            f'{class_name:<{col_class_w}} | '
            f'{p_display:<{col_param_w}} | '
            f'{type_name:<{col_type_w}} | '
            f'{def_name:<{col_def_w}} | '
        )
        rem_w = max(width - len(line_left), 1)
        print(f'{line_left}{exec_str:<{rem_w}}')

    print('=' * width)
    sys.path.pop(0)


if __name__ == '__main__':
    run_inspection()
