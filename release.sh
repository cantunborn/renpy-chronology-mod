#!/usr/bin/env bash
# Usage: ./release.sh v0.1.0 ["Release title"]
# Requires: gh (GitHub CLI), zip

set -e

VERSION="${1:?Usage: ./release.sh <version-tag> [title]}"
TITLE="${2:-Chronology Mod $VERSION}"
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
ZIP_NAME="chronology-mod-${VERSION}.zip"
TMP_DIR="$(mktemp -d)"
MOD_DIR="$TMP_DIR/game/renpy-chronology-mod"

echo "→ Building $ZIP_NAME"

# ── Copy mod files ─────────────────────────────────────────────────────────────
mkdir -p "$MOD_DIR"
cp "$REPO_ROOT"/timeline_init.rpy \
   "$REPO_ROOT"/timeline_hooks.rpy \
   "$REPO_ROOT"/timeline_screen.rpy \
   "$REPO_ROOT"/timeline_save_hooks.rpy \
   "$REPO_ROOT"/timeline_tests.rpy \
   "$MOD_DIR/"
cp -r "$REPO_ROOT/fonts" "$MOD_DIR/fonts"

# ── Generate README.txt (strip dev notes, convert markdown) ───────────────────
python3 - "$REPO_ROOT/README.md" "$MOD_DIR/README.txt" <<'PYEOF'
import sys, re

src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()

# Drop <details> block (dev notes)
text = re.sub(r'<details>.*?</details>', '', text, flags=re.DOTALL).strip()

lines = text.splitlines()
out = []

for line in lines:
    # H1
    if re.match(r'^# ', line):
        title = line[2:].strip()
        out.append(title.upper())
        out.append("=" * len(title))
        continue
    # H2
    if re.match(r'^## ', line):
        title = line[3:].strip()
        out.append("")
        out.append(title.upper())
        out.append("-" * len(title))
        continue
    # H3
    if re.match(r'^### ', line):
        title = line[4:].strip()
        out.append("")
        out.append(title)
        continue
    # Horizontal rule
    if re.match(r'^---+$', line.strip()):
        continue
    # Table separator row
    if re.match(r'^\|[-| :]+\|$', line.strip()):
        continue
    # Table data row — strip pipes, align columns
    if line.strip().startswith("|") and line.strip().endswith("|"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        out.append("  ".join(f"{c:<20}" for c in cells).rstrip())
        continue
    # Strip inline markdown: **bold**, *italic*, `code`, [text](url)
    line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
    line = re.sub(r'\*(.+?)\*',     r'\1', line)
    line = re.sub(r'`(.+?)`',       r'\1', line)
    line = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', line)
    out.append(line)

open(dst, "w", encoding="utf-8").write("\n".join(out).strip() + "\n")
print(f"  README.txt written ({len(out)} lines)")
PYEOF

# ── Zip ────────────────────────────────────────────────────────────────────────
(cd "$TMP_DIR" && zip -r "$REPO_ROOT/$ZIP_NAME" game/ -x "*.DS_Store")
echo "→ Created $ZIP_NAME"

# ── Tag ────────────────────────────────────────────────────────────────────────
if ! git -C "$REPO_ROOT" rev-parse "$VERSION" >/dev/null 2>&1; then
    git -C "$REPO_ROOT" tag "$VERSION"
    echo "→ Tagged $VERSION"
fi

echo ""
echo "✓ Done. Upload the release manually:"
echo "  1. Go to https://github.com/cantunborn/renpy-chronology-mod/releases/new"
echo "  2. Set tag: $VERSION"
echo "  3. Set title: $TITLE"
echo "  4. Drag in: $REPO_ROOT/$ZIP_NAME"
echo "  5. Publish"
rm -rf "$TMP_DIR"
