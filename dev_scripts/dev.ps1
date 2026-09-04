$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# --------------------------------------------------
# Project information
# --------------------------------------------------

$ProjectName = ""

if (Test-Path "pyproject.toml") {
    $NameLine = Get-Content "pyproject.toml" |
        Where-Object { $_ -match '^name\s*=' } |
        Select-Object -First 1

    if ($NameLine -match '^name\s*=\s*["'']([^"'']+)["'']') {
        $ProjectName = $Matches[1]
    }
}

if ([string]::IsNullOrWhiteSpace($ProjectName)) {
    $ProjectName = "Python Project"
}

Write-Host "========================================"
Write-Host " $ProjectName Development Helper"
Write-Host "========================================"
Write-Host ""

# --------------------------------------------------
# Tool detection
# --------------------------------------------------

Write-Host "[*] Checking development tools..."

$PythonCommand = $null

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = "python"
}

if (-not $PythonCommand) {
    Write-Host "[!] Python was not found."
    Write-Host "    Please install a supported Python version."
    exit 1
}

$PythonVersion = & $PythonCommand --version 2>&1
Write-Host "[+] Python: $PythonVersion"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[!] uv was not found."
    Write-Host "    Please install uv and try again."
    exit 1
}

$UvVersion = uv --version
Write-Host "[+] uv: $UvVersion"

Write-Host ""

# --------------------------------------------------
# Command helper
# --------------------------------------------------

function Invoke-CommandChecked {
    param (
        [Parameter(Mandatory = $true)]
        [string]$Command,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "----------------------------------------"
    Write-Host "[>] $Command $($Arguments -join ' ')"
    Write-Host "----------------------------------------"
    Write-Host ""

    & $Command @Arguments

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[!] Command failed with exit code $LASTEXITCODE."
        return $false
    }

    Write-Host ""
    Write-Host "[+] Command completed successfully."
    return $true
}

# --------------------------------------------------
# Commands
# --------------------------------------------------

function Sync-Environment {
    return Invoke-CommandChecked "uv" @("sync")
}

function Run-Lint {
    return Invoke-CommandChecked "uv" @("run", "ruff", "check", ".")
}

function Run-FormatCheck {
    return Invoke-CommandChecked "uv" @("run", "ruff", "format", "--check", ".")
}

function Run-Format {
    return Invoke-CommandChecked "uv" @("run", "ruff", "format", ".")
}

function Run-TypeCheck {
    return Invoke-CommandChecked "uv" @("run", "pyright")
}

function Run-Tests {
    return Invoke-CommandChecked "uv" @("run", "pytest")
}

function Run-AllChecks {
    Write-Host ""
    Write-Host "========================================"
    Write-Host " Running all checks"
    Write-Host "========================================"

    if (-not (Sync-Environment)) { return $false }
    if (-not (Run-Lint)) { return $false }
    if (-not (Run-FormatCheck)) { return $false }
    if (-not (Run-TypeCheck)) { return $false }
    if (-not (Run-Tests)) { return $false }

    Write-Host ""
    Write-Host "========================================"
    Write-Host " All checks passed!"
    Write-Host "========================================"

    return $true
}

function Build-Package {
    return Invoke-CommandChecked "uv" @("build")
}

function Show-Versions {
    Write-Host ""
    Write-Host "Python:"
    & $PythonCommand --version

    Write-Host ""
    Write-Host "uv:"
    uv --version

    Write-Host ""
    Write-Host "Project Python:"
    uv run python --version
}

# --------------------------------------------------
# Menu
# --------------------------------------------------

while ($true) {
    Write-Host ""
    Write-Host "========================================"
    Write-Host " Development Menu"
    Write-Host "========================================"
    Write-Host ""
    Write-Host " 1) Sync environment"
    Write-Host " 2) Lint"
    Write-Host " 3) Format check"
    Write-Host " 4) Format"
    Write-Host " 5) Type check"
    Write-Host " 6) Test"
    Write-Host " 7) Run all checks"
    Write-Host " 8) Build package"
    Write-Host " 9) Show tool versions"
    Write-Host " 0) Exit"
    Write-Host ""

    $Choice = Read-Host "Select an option"

    switch ($Choice) {
        "1" {
            Sync-Environment | Out-Null
        }

        "2" {
            Run-Lint | Out-Null
        }

        "3" {
            Run-FormatCheck | Out-Null
        }

        "4" {
            Run-Format | Out-Null
        }

        "5" {
            Run-TypeCheck | Out-Null
        }

        "6" {
            Run-Tests | Out-Null
        }

        "7" {
            Run-AllChecks | Out-Null
        }

        "8" {
            Build-Package | Out-Null
        }

        "9" {
            Show-Versions
        }

        "0" {
            Write-Host ""
            Write-Host "Bye!"
            exit 0
        }

        default {
            Write-Host ""
            Write-Host "[!] Invalid option."
        }
    }

    Write-Host ""
    Read-Host "Press Enter to continue" | Out-Null
}
