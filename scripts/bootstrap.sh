#!/bin/sh
set -eu

root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root_dir"

git submodule update --init --recursive

# Local fixes on top of the MathCAT and UnicodeMathML submodules (see each
# patch's header).
apply_patches() {
    submodule=$1
    for patch in "$root_dir"/patches/"$2"/*.patch; do
        [ -e "$patch" ] || continue
        if git -C "$submodule" apply --reverse --check "$patch" >/dev/null 2>&1; then
            continue  # Already applied.
        fi
        if ! git -C "$submodule" apply "$patch"; then
            printf '%s\n' "Patch $(basename "$patch") does not apply to $submodule." >&2
            exit 1
        fi
    done
}
apply_patches MathCAT mathcat
apply_patches UnicodeMathML unicodemathml

export UV_CACHE_DIR="$root_dir/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$root_dir/.tools/python"
export CARGO_HOME="$root_dir/.tools/cargo"
export RUSTUP_HOME="$root_dir/.tools/rustup"

if command -v uv >/dev/null 2>&1; then
    uv_cmd=uv
elif [ -x "$root_dir/.tools/uv" ]; then
    uv_cmd="$root_dir/.tools/uv"
else
    mkdir -p "$root_dir/.tools"
    curl -LsSf https://astral.sh/uv/install.sh | \
        UV_INSTALL_DIR="$root_dir/.tools" UV_NO_MODIFY_PATH=1 sh
    uv_cmd="$root_dir/.tools/uv"
fi

if [ -x "$CARGO_HOME/bin/cargo" ]; then
    PATH="$CARGO_HOME/bin:$PATH"
elif ! command -v cargo >/dev/null 2>&1; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
        sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable
    PATH="$CARGO_HOME/bin:$PATH"
fi
export PATH

python_request=3.14
if [ "$(uname -s)" = "Darwin" ]; then
    # wxPython needs a macOS Framework build. UV's standalone CPython builds
    # are excellent for CLI workloads, but cannot create an AppKit wx.App.
    python_request=
    for candidate in python3.14 python3.13 python3.12 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && \
            "$candidate" -c 'import sysconfig; raise SystemExit(not bool(sysconfig.get_config_var("PYTHONFRAMEWORK")))'
        then
            python_request=$(command -v "$candidate")
            break
        fi
    done
    if [ -z "$python_request" ]; then
        printf '%s\n' \
            "On macOS, MateX needs a Framework build of Python for wxPython." \
            "Install Python from Homebrew or python.org, then run this script again." >&2
        exit 1
    fi
else
    "$uv_cmd" python install "$python_request"
fi

"$uv_cmd" sync --python "$python_request"
"$uv_cmd" run python -m unittest discover -s tests -v

printf '%s\n' "MateX is ready. Start it with: $uv_cmd run matex"
