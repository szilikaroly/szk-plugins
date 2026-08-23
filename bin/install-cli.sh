#!/usr/bin/env bash
# Install the global CLI launchers so the szk-plugins engines work from any shell
# on this machine — always running the real source .py (never a bytecode-only
# copy), so no session has to fall back to a degraded implementation.
#
#   ./bin/install-cli.sh            # symlink into ~/.local/bin (default)
#   BIN_DIR=/usr/local/bin ./bin/install-cli.sh
#
# Idempotent and safe to re-run (e.g. after pulling updates on another machine).
set -euo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$BIN_DIR"

for tool in figure-forge presubmit science-monitor \
             composer validator academic-editor; do
  src="$REPO/bin/$tool"
  dst="$BIN_DIR/$tool"
  ln -sf "$src" "$dst"
  chmod +x "$src"
  echo "linked $dst -> $src"
done

case ":$PATH:" in
  *":$BIN_DIR:"*) : ;;
  *) echo "NOTE: $BIN_DIR is not on your PATH — add it in your shell profile:"
     echo "      export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

echo
echo "Verify:"
echo "  figure-forge selftest     # 11 checks"
echo "  presubmit selftest        # 10 planted mistakes caught"
echo "  science-monitor status    # the manuscript pipeline"
echo "  composer selftest         # the 5D gate and the PROSPERO rules"
echo "  validator --list          # 12 appraisal instruments"
echo "  academic-editor selftest  # the checker and both .docx writers"
echo
echo "Or all of them at once:  ./bin/selftest-all.sh"
