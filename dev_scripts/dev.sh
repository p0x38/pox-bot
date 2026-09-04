#!/usr/bin/env bash

set -u

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

# --------------------------------------------------
# Project information
# --------------------------------------------------

PROJECT_NAME="$(awk -F'"' '/^name = / {print $2; exit}' pyproject.toml)"

if [[ -z "$PROJECT_NAME" ]]; then
    PROJECT_NAME="Python Project"
fi

echo "========================================"
echo " $PROJECT_NAME Development Helper"
echo "========================================"
echo

# --------------------------------------------------
# Tool detection
# --------------------------------------------------

echo "[*] Checking development tools..."

PYTHON_CMD=""

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
fi

if [[ -z "$PYTHON_CMD" ]]; then
    echo "[!] Python was not found."
    echo "    Please install a supported Python version."
    exit 1
fi

PYTHON_VERSION="$($PYTHON_CMD --version 2>&1)"
echo "[+] Python: $PYTHON_VERSION"

if ! command -v uv >/dev/null 2>&1; then
    echo "[!] uv was not found."
    echo "    Please install uv and try again."
    exit 1
fi

echo "[+] uv: $(uv --version)"

echo

# --------------------------------------------------
# Command helpers
# --------------------------------------------------

run_command() {
    echo
    echo "----------------------------------------"
    echo "[>] $*"
    echo "----------------------------------------"
    echo

    "$@"
    local status=$?

    if [[ $status -ne 0 ]]; then
        echo
        echo "[!] Command failed with exit code $status."
        return "$status"
    fi

    echo
    echo "[+] Command completed successfully."
    return 0
}

sync_environment() {
    run_command uv sync
}

run_lint() {
    run_command uv run ruff check .
}

run_format_check() {
    run_command uv run ruff format --check .
}

run_format() {
    run_command uv run ruff format .
}

run_typecheck() {
    run_command uv run pyright
}

run_tests() {
    run_command uv run pytest
}

run_all_checks() {
    echo
    echo "========================================"
    echo " Running all checks"
    echo "========================================"

    sync_environment || return $?
    run_lint || return $?
    run_format_check || return $?
    run_typecheck || return $?
    run_tests || return $?

    echo
    echo "========================================"
    echo " All checks passed!"
    echo "========================================"
}

build_package() {
    run_command uv build
}

show_versions() {
    echo
    echo "Python:"
    "$PYTHON_CMD" --version

    echo
    echo "uv:"
    uv --version

    echo
    echo "Project Python:"
    uv run python --version
}

# --------------------------------------------------
# Menu
# --------------------------------------------------

while true; do
    echo
    echo "========================================"
    echo " Development Menu"
    echo "========================================"
    echo
    echo "  1) Sync environment"
    echo "  2) Lint"
    echo "  3) Format check"
    echo "  4) Format"
    echo "  5) Type check"
    echo "  6) Test"
    echo "  7) Run all checks"
    echo "  8) Build package"
    echo "  9) Show tool versions"
    echo "  0) Exit"
    echo

    read -r -p "Select an option: " choice

    case "$choice" in
        1)
            sync_environment
            ;;
        2)
            run_lint
            ;;
        3)
            run_format_check
            ;;
        4)
            run_format
            ;;
        5)
            run_typecheck
            ;;
        6)
            run_tests
            ;;
        7)
            run_all_checks
            ;;
        8)
            build_package
            ;;
        9)
            show_versions
            ;;
        0)
            echo
            echo "Bye!"
            exit 0
            ;;
        *)
            echo
            echo "[!] Invalid option."
            ;;
    esac

    echo
    read -r -p "Press Enter to continue..." _
done
