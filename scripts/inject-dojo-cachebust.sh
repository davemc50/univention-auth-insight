#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Wire umc/web/cache_bust into dojoConfig.cacheBust so every Auth Insight
# (and all UMC module) deploy forces a new JS URL. UCS sets the UCR key but
# never injects it into the frontend on this release.
set -euo pipefail

INDEX="${1:-/usr/share/univention-management-console-frontend/index.html}"
BUST="$(ucr get umc/web/cache_bust 2>/dev/null || true)"
if [[ -z "$BUST" ]]; then
  BUST="$(date +%s)"
  ucr set "umc/web/cache_bust=$BUST" >/dev/null
fi

python3 - "$INDEX" "$BUST" <<'PY'
import pathlib, sys, re

index_path = pathlib.Path(sys.argv[1])
bust = sys.argv[2]
text = index_path.read_text(encoding="utf-8")

snippet = (
    "\t\t<script type=\"text/javascript\">\n"
    "\t\t\t/*authin-dojo-cachebust*/\n"
    "\t\t\tdojoConfig = (typeof dojoConfig === 'undefined') ? {} : dojoConfig;\n"
    f"\t\t\tdojoConfig.cacheBust = '{bust}';\n"
    "\t\t</script>\n"
)

marker_re = re.compile(
    r"\t\t<script type=\"text/javascript\">\n"
    r"\t\t\t/\*authin-dojo-cachebust\*/\n"
    r".*?"
    r"\t\t</script>\n",
    re.DOTALL,
)

if marker_re.search(text):
    text = marker_re.sub(snippet, text, count=1)
else:
    anchor = '\t\t<script type="text/javascript" src="/univention/js/config.js"></script>\n'
    if anchor not in text:
        raise SystemExit(f"anchor not found in {index_path}")
    text = text.replace(anchor, anchor + snippet, 1)

index_path.write_text(text, encoding="utf-8")
print(f"dojoConfig.cacheBust={bust} -> {index_path}")
PY
