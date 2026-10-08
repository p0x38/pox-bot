"""Audit likely user-facing string literals not routed through the translator.

This is a heuristic audit: it checks common Discord command, response, embed,
choice, and UI APIs. Dynamic strings assembled elsewhere may need manual review.
"""

import argparse
import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

USER_RESPONSE_METHODS = {
    'send',
    'send_message',
    'reply',
    'edit',
    'edit_original_response',
    'send_modal',
}
EMBED_TEXT_KEYWORDS = {'title', 'description', 'name', 'value', 'text'}
UI_CLASSES = {'Button', 'SelectOption', 'TextInput', 'Modal'}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    category: str
    text: str


def call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = call_name(node.value)
        return f'{prefix}.{node.attr}' if prefix else node.attr
    return ''


def literal_text(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append('{…}')
        return ''.join(parts)
    return None


def is_translated(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and call_name(node.func).split('.')[-1] in {
        'T',
        'locale_str',
    }


class CandidateVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.findings: list[Finding] = []

    def add(self, node: ast.expr, category: str) -> None:
        if is_translated(node):
            return
        text = literal_text(node)
        if text is not None and text.strip():
            self.findings.append(
                Finding(self.path, node.lineno, category, text.replace('\n', '\\n')),
            )

    def visit_Call(self, node: ast.Call) -> None:
        name = call_name(node.func)
        method = name.rsplit('.', maxsplit=1)[-1]
        if method in {'command', 'group', 'Group'}:
            for keyword in node.keywords:
                if keyword.arg == 'description':
                    self.add(keyword.value, 'command description')
        elif method == 'describe':
            for keyword in node.keywords:
                self.add(keyword.value, 'command parameter')

        if method in USER_RESPONSE_METHODS:
            for arg in node.args:
                self.add(arg, 'Discord response')
            for keyword in node.keywords:
                if keyword.arg in {'content', 'embed'}:
                    self.add(keyword.value, 'Discord response')

        if method == 'Embed':
            for keyword in node.keywords:
                if keyword.arg in {'title', 'description'}:
                    self.add(keyword.value, 'embed text')

        if method in UI_CLASSES | {'Choice'}:
            for keyword in node.keywords:
                if keyword.arg in {
                    'label',
                    'placeholder',
                    'title',
                    'description',
                    'name',
                }:
                    self.add(
                        keyword.value, 'UI label' if method != 'Choice' else 'choice'
                    )

        if method in {'add_field', 'set_author', 'set_footer'}:
            for keyword in node.keywords:
                if keyword.arg in EMBED_TEXT_KEYWORDS:
                    self.add(keyword.value, 'embed text')

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr in {
                'title',
                'description',
                'label',
            }:
                self.add(node.value, 'user-facing attribute')
        self.generic_visit(node)


def python_files(paths: Iterable[Path]) -> list[Path]:
    files = []
    for path in paths:
        if path.is_file() and path.suffix == '.py':
            files.append(path)
        elif path.is_dir():
            files.extend(path.rglob('*.py'))
    return sorted(set(files))


def scan(files: Iterable[Path]) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    errors: list[str] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except (OSError, SyntaxError) as error:
            errors.append(f'{path}: {error}')
            continue
        visitor = CandidateVisitor(path)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    findings.sort(
        key=lambda finding: (str(finding.path), finding.line, finding.category)
    )
    return findings, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'paths',
        nargs='*',
        type=Path,
        help='Python files or directories (default: src/poxbot)',
    )
    parser.add_argument(
        '--include-legacy',
        action='store_true',
        help='Include cogs-legacy when scanning the repository by default.',
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    paths = args.paths or [root / 'src' / 'poxbot']
    if args.include_legacy and not args.paths:
        paths.append(root / 'cogs-legacy')
    files = [
        path
        for path in python_files(paths)
        if args.include_legacy or 'cogs-legacy' not in path.parts
    ]
    findings, errors = scan(files)

    for finding in findings:
        try:
            display_path = finding.path.resolve().relative_to(root)
        except ValueError:
            display_path = finding.path
        sys.stdout.write(
            f'{display_path}:{finding.line}: [{finding.category}] {finding.text}\n',
        )

    if findings:
        sys.stdout.write(f'\n{len(findings)} likely untranslated string(s) found.\n')
    else:
        sys.stdout.write('No likely untranslated strings found.\n')
    if errors:
        sys.stdout.write('\nFiles that could not be scanned:\n')
        sys.stdout.write('\n'.join(errors) + '\n')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
