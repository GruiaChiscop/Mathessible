# Prepares a checkout on Windows, as scripts/bootstrap.sh does on macOS and Linux: the submodules and
# Mathessible's patches to them, uv and Rust (into .tools when missing), the native MathCAT extension, the
# tests. Run it from scripts\bootstrap.bat, or: powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
#
# The extension is compiled with Visual Studio's C++ build tools and their Clang (liblouis is built with
# clang-cl, as NVDA builds it); they need an administrator to install, so the script says how and stops.
# On ARM64, cryptography (through pypdf) has no wheel and is built against OpenSSL, which vcpkg builds once
# (into .tools\vcpkg, or the one VCPKG_ROOT names).

# Programs are checked by their exit code (Invoke-Native): with "Stop", Windows PowerShell 5.1 takes
# what git and uv write to a redirected stderr (their progress) for an error.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root -ErrorAction Stop

function Invoke-Native([string]$what, [scriptblock]$command) {
    & $command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "$what failed (exit code $LASTEXITCODE)."
        exit $LASTEXITCODE
    }
}

Invoke-Native "Fetching the submodules" { git submodule update --init --recursive }

# Local fixes on top of the MathCAT and UnicodeMathML submodules (see each patch's header).
function Install-Patches([string]$submodule, [string]$folder) {
    foreach ($patch in Get-ChildItem "$root\patches\$folder\*.patch" | Sort-Object Name) {
        cmd /c "git -C $submodule apply --reverse --check `"$($patch.FullName)`" >nul 2>&1"
        if ($LASTEXITCODE -eq 0) { continue }  # Already applied.
        cmd /c "git -C $submodule apply `"$($patch.FullName)`""
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Patch $($patch.Name) does not apply to $submodule."
            exit 1
        }
    }
}
Install-Patches "MathCAT" "mathcat"
Install-Patches "UnicodeMathML" "unicodemathml"

$env:UV_CACHE_DIR = "$root\.uv-cache"
$env:UV_PYTHON_INSTALL_DIR = "$root\.tools\python"
# The machine's processor, also from a 32-bit or emulated PowerShell.
$architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
$arm64 = $architecture -eq "ARM64"

if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uv = "uv"
} else {
    $uv = "$root\.tools\uv.exe"
    if (-not (Test-Path $uv)) {
        $env:UV_INSTALL_DIR = "$root\.tools"
        $env:UV_NO_MODIFY_PATH = "1"
        Invoke-RestMethod https://astral.sh/uv/install.ps1 -ErrorAction Stop | Invoke-Expression
    }
}

if (Test-Path "$root\.tools\cargo\bin\cargo.exe") {
    $env:CARGO_HOME = "$root\.tools\cargo"
    $env:RUSTUP_HOME = "$root\.tools\rustup"
    $env:Path = "$env:CARGO_HOME\bin;$env:Path"
} elseif (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    $env:CARGO_HOME = "$root\.tools\cargo"
    $env:RUSTUP_HOME = "$root\.tools\rustup"
    $triple = if ($arm64) { "aarch64-pc-windows-msvc" } else { "x86_64-pc-windows-msvc" }
    $installer = "$root\.tools\rustup-init.exe"
    New-Item -ItemType Directory -Force "$root\.tools" -ErrorAction Stop | Out-Null
    Invoke-WebRequest "https://static.rust-lang.org/rustup/dist/$triple/rustup-init.exe" -OutFile $installer -ErrorAction Stop
    Invoke-Native "Installing Rust" {
        & $installer -y --no-modify-path --profile minimal --default-toolchain stable --default-host $triple
    }
    $env:Path = "$env:CARGO_HOME\bin;$env:Path"
}

# Visual Studio's C++ tools for this processor, and their Clang.
$tools = if ($arm64) { "Microsoft.VisualStudio.Component.VC.Tools.ARM64" } else { "Microsoft.VisualStudio.Component.VC.Tools.x86.x64" }
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vs = if (Test-Path $vswhere) { & $vswhere -latest -products * -requires $tools -property installationPath } else { $null }
$llvm = if ($arm64) { "ARM64" } else { "x64" }
if (-not $vs -or -not (Test-Path "$vs\VC\Tools\Llvm\$llvm\bin\clang-cl.exe")) {
    Write-Host "Mathessible's MathCAT extension is compiled with Visual Studio's C++ build tools and their Clang."
    Write-Host "Install them (as an administrator), then run this script again:"
    Write-Host ""
    Write-Host "  winget install Microsoft.VisualStudio.2022.BuildTools --override `"--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --add $tools --add Microsoft.VisualStudio.Component.VC.Llvm.Clang --add Microsoft.VisualStudio.Component.VC.Llvm.ClangToolset --includeRecommended`""
    exit 1
}
$vcvars = if ($arm64) { "vcvarsarm64.bat" } else { "vcvars64.bat" }
cmd /c "`"$vs\VC\Auxiliary\Build\$vcvars`" >nul && set" | ForEach-Object {
    if ($_ -match "^([^=]+)=(.*)$") { Set-Item "env:$($Matches[1])" $Matches[2] }
}
$env:Path = "$vs\VC\Tools\Llvm\$llvm\bin;$env:Path"

if ($arm64 -and -not $env:OPENSSL_DIR) {
    $vcpkg = if ($env:VCPKG_ROOT -and (Test-Path "$env:VCPKG_ROOT\vcpkg.exe")) { $env:VCPKG_ROOT } else { "$root\.tools\vcpkg" }
    $openssl = "$vcpkg\installed\arm64-windows-static-md"
    if (-not (Test-Path "$openssl\include\openssl")) {
        Write-Host "Building OpenSSL with vcpkg, once (several minutes)..."
        if (-not (Test-Path "$vcpkg\vcpkg.exe")) {
            if (-not (Test-Path $vcpkg)) {
                Invoke-Native "Fetching vcpkg" { git clone --depth 1 https://github.com/microsoft/vcpkg.git $vcpkg }
            }
            Invoke-Native "Preparing vcpkg" { & "$vcpkg\bootstrap-vcpkg.bat" -disableMetrics }
        }
        Invoke-Native "Building OpenSSL" { & "$vcpkg\vcpkg.exe" install openssl:arm64-windows-static-md }
    }
    $env:OPENSSL_DIR = $openssl
    $env:OPENSSL_STATIC = "1"
}

Invoke-Native "Installing Python" { & $uv python install 3.14 }
Invoke-Native "Installing Mathessible's dependencies" { & $uv sync --python 3.14 }
Invoke-Native "The tests" { & $uv run python -m unittest discover -s tests -v }

Write-Host "Mathessible is ready. Start it with: $uv run mathessible"
Write-Host "After an update, run this script again: it rebuilds the MathCAT extension."
