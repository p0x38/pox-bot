#!/usr/bin/env python3
"""Find statically referenced translator keys missing from locale JSON files.

By default, scans ``src/poxbot`` and checks every locale under
``src/poxbot/assets/locales``. Dynamic keys (for example ``T(f'{prefix}.{name}')``)
are listed separately because their complete value cannot be determined statically.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TRANSLATOR_CALLS = {'T', 'translate_string', 'translate_plural', 'locale_str'}
SKIP_DIRECTORY_NAMES = {
    '.git',
    '.mypy_cache',
    '.pytest_cache',
    '.ruff_cache',
    '.venv',
    '__pycache__',
    'build',
    'dist',
    'node_modules',
    'venv',
}


@dataclass(frozen=True)
class Reference:
    path: Path
    line: int


@dataclass(frozen=True)
class DynamicReference:
    path: Path
    line: int
    expression: str


def call_name(node: ast.expr) -> str:
    """Return a dotted name for a call target, if it has one."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = call_name(node.value)
        return f'{prefix}.{node.attr}' if prefix else node.attr
    return ''


def static_strings(node: ast.expr) -> tuple[list[str], bool]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value], True

    if isinstance(node, ast.JoinedStr):
        values: list[str] = []

        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(
                value.value,
                str,
            ):
                return [], False

            values.append(value.value)

        return [''.join(values)], True

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, left_static = static_strings(node.left)
        right, right_static = static_strings(node.right)
        if left_static and right_static and len(left) == 1 and len(right) == 1:
            return [left[0] + right[0]], True
        return [], False

    if isinstance(node, (ast.List, ast.Tuple)):
        values: list[str] = []
        fully_static = True
        for element in node.elts:
            element_values, element_static = static_strings(element)
            values.extend(element_values)
            fully_static = fully_static and element_static
        return values, fully_static

    return [], False


def translator_key_argument(call: ast.Call) -> ast.expr | None:
    """Get the expression that contains the key for a supported translator call."""
    # A named `key=` is used by some locale_str wrappers and takes precedence.
    for keyword in call.keywords:
        if keyword.arg == 'key':
            return keyword.value

    if call.args:
        return call.args[0]

    for keyword in call.keywords:
        if keyword.arg in {'string', 'text'}:
            return keyword.value

    return None


class TranslatorCallVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.references: dict[str, list[Reference]] = defaultdict(list)
        self.dynamic_references: list[DynamicReference] = []

    def visit_Call(self, node: ast.Call) -> None:
        function_name = call_name(node.func).rsplit('.', maxsplit=1)[-1]
        if function_name in TRANSLATOR_CALLS:
            key_node = translator_key_argument(node)
            if key_node is not None:
                keys, is_static = static_strings(key_node)
                for key in keys:
                    if key.strip():
                        self.references[key].append(Reference(self.path, node.lineno))

                if not is_static:
                    self.dynamic_references.append(
                        DynamicReference(
                            self.path,
                            node.lineno,
                            ast.unparse(key_node),
                        ),
                    )

        self.generic_visit(node)


def python_files(paths: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix == '.py':
            files.add(path)
            continue
        if not path.is_dir():
            continue
        for candidate in path.rglob('*.py'):
            if not any(part in SKIP_DIRECTORY_NAMES for part in candidate.parts):
                files.add(candidate)
    return sorted(files, key=str)


def scan_python(
    files: Iterable[Path],
) -> tuple[dict[str, list[Reference]], list[DynamicReference], list[str]]:
    references: dict[str, list[Reference]] = defaultdict(list)
    dynamic_references: list[DynamicReference] = []
    errors: list[str] = []

    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as error:
            errors.append(f'{path}: {error}')
            continue

        visitor = TranslatorCallVisitor(path)
        visitor.visit(tree)
        for key, locations in visitor.references.items():
            references[key].extend(locations)
        dynamic_references.extend(visitor.dynamic_references)

    return references, dynamic_references, errors


def flatten_json(value: Any, prefix: str, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_key = f'{prefix}.{key}' if prefix else str(key)
            flatten_json(child, child_key, output)
    elif prefix:
        output[prefix] = value


def load_locale(
    locale_directory: Path,
) -> tuple[dict[str, Any], list[str], int]:
    translations: dict[str, Any] = {}
    errors: list[str] = []
    file_count = 0

    for path in sorted(locale_directory.rglob('*.json')):
        file_count += 1
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError, UnicodeError) as error:
            errors.append(f'{path}: {error}')
            continue

        relative_without_suffix = path.relative_to(locale_directory).with_suffix('')
        namespace = '.'.join(relative_without_suffix.parts)
        flatten_json(data, namespace, translations)

    return translations, errors, file_count


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def references_text(
    locations: list[Reference],
    root: Path,
    limit: int = 3,
) -> str:
    unique = sorted(
        {(display_path(item.path, root), item.line) for item in locations},
    )
    shown = ', '.join(f'{path}:{line}' for path, line in unique[:limit])
    if len(unique) > limit:
        shown += f', … (+{len(unique) - limit} more)'
    return shown


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    default_locale_dir = root / 'src' / 'poxbot' / 'assets' / 'locales'
    default_source_dir = root / 'src' / 'poxbot'

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'paths',
        nargs='*',
        type=Path,
        help='Python files/directories to scan (default: src/poxbot)',
    )
    parser.add_argument(
        '--locales-dir',
        type=Path,
        default=default_locale_dir,
        help='Locale root containing one directory per locale',
    )
    parser.add_argument(
        '--locales',
        nargs='+',
        help='Locales to check (default: every locale directory found)',
    )
    parser.add_argument(
        '--show-dynamic',
        action='store_true',
        help='List translator calls whose keys cannot be determined statically',
    )
    args = parser.parse_args()

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

    scan_paths = args.paths or [default_source_dir]
    files = python_files(scan_paths)
    if not files:
        print('Error: no Python files found to scan.', file=sys.stderr)
        return 2

    references, dynamic_references, scan_errors = scan_python(files)
    if scan_errors:
        print('Python files that could not be scanned:', file=sys.stderr)
        for error in scan_errors:
            print(f'  {error}', file=sys.stderr)

    if not args.locales_dir.is_dir():
        print(f'Error: locale directory not found: {args.locales_dir}', file=sys.stderr)
        return 2

    if args.locales:
        locale_names = args.locales
    else:
        locale_names = sorted(
            path.name
            for path in args.locales_dir.iterdir()
            if path.is_dir() and any(path.rglob('*.json'))
        )

    if not locale_names:
        print(
            f'Error: no locale directories found in {args.locales_dir}', file=sys.stderr
        )
        return 2

    translations_by_locale: dict[str, dict[str, Any]] = {}
    locale_errors: list[str] = []
    file_count = 0

    for locale in locale_names:
        locale_directory = args.locales_dir / locale
        if not locale_directory.is_dir():
            locale_errors.append(f'Locale directory not found: {locale_directory}')
            continue
        translations, errors, count = load_locale(locale_directory)
        translations_by_locale[locale] = translations
        locale_errors.extend(errors)
        file_count += count

    if locale_errors:
        print('Locale files that could not be loaded:', file=sys.stderr)
        for error in locale_errors:
            print(f'  {error}', file=sys.stderr)

    loaded_locales = sorted(translations_by_locale)
    if not loaded_locales:
        return 2

    missing_everywhere: dict[str, list[str]] = {}
    missing_somewhere: dict[str, list[str]] = {}
    empty_values: list[tuple[str, str, list[Reference]]] = []

    for key in sorted(references):
        missing_locales = [
            locale
            for locale in loaded_locales
            if key not in translations_by_locale[locale]
        ]
        if len(missing_locales) == len(loaded_locales):
            missing_everywhere[key] = missing_locales
        elif missing_locales:
            missing_somewhere[key] = missing_locales

        for locale in loaded_locales:
            locale_translations = translations_by_locale[locale]
            if key not in locale_translations:
                continue

            value = locale_translations[key]
            if not isinstance(value, str) or not value.strip():
                # Non-string values are also suspect for a translator key.
                empty_values.append((locale, key, references[key]))

    print(f'Scanned {len(files)} Python file(s).')
    print(f'Found {len(references)} distinct static translator key(s).')
    print(f'Loaded {file_count} locale JSON file(s).')
    print(f'Checked {len(loaded_locales)} locale(s): {", ".join(loaded_locales)}')

    if missing_everywhere:
        print(f'\nMissing from every checked locale ({len(missing_everywhere)}):')
        for key in missing_everywhere:
            print(f'  {key} — used at {references_text(references[key], root)}')

    if missing_somewhere:
        print(f'\nMissing from some checked locales ({len(missing_somewhere)}):')
        for key, missing_locales in missing_somewhere.items():
            print(
                f'  {key} — missing in {", ".join(missing_locales)}; '
                f'used at {references_text(references[key], root)}',
            )

    if empty_values:
        print(f'\nEmpty/non-string translation values ({len(empty_values)}):')
        for locale, key, locations in sorted(
            empty_values, key=lambda item: (item[0], item[1])
        ):
            print(
                f'  [{locale}] {key} — used at {references_text(locations, root)}',
            )

    if args.show_dynamic and dynamic_references:
        print(
            f'\nDynamic translator keys that need manual review '
            f'({len(dynamic_references)}):',
        )
        unique_dynamic = sorted(
            {
                (
                    display_path(item.path, root),
                    item.line,
                    item.expression,
                )
                for item in dynamic_references
            },
        )
        for path, line, expression in unique_dynamic:
            print(f'  {path}:{line}: {expression}')
    elif dynamic_references:
        print(
            f'\nSkipped {len(dynamic_references)} dynamic translator call(s); '
            'rerun with --show-dynamic to list them.',
        )

    if not missing_everywhere and not missing_somewhere and not empty_values:
        print('\nAll statically referenced translator keys are defined and non-empty.')

    if scan_errors or locale_errors:
        return 2
    return 1 if missing_everywhere or missing_somewhere or empty_values else 0


if __name__ == '__main__':
    raise SystemExit(main())
