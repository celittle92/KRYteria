#!/usr/bin/env bash
#
# Re-take the report's figures from the running app.
#
# Must be run from a normal terminal, NOT from Claude Code's sandboxed shell: Chrome
# needs a unix domain socket for its ProcessSingleton and the sandbox refuses to create
# one, so it aborts before loading anything.
#
# Start the app first (the preview server on 8077, or uvicorn yourself), then:
#
#     ./tools/screenshots.sh [port]
#
# Each shot is a direct `?demo=<handle>` link, which is why no clicking is needed — the
# app signs itself into that demo character and lands on the route in the URL.

set -euo pipefail

PORT="${1:-8077}"
BASE="http://localhost:${PORT}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$HERE/output/screenshots"
PROFILE="$(mktemp -d)"

[ -x "$CHROME" ] || { echo "Chrome not found at $CHROME" >&2; exit 1; }
curl -sf "$BASE/api/health" >/dev/null || {
  echo "Nothing answering on $BASE — start the app first." >&2; exit 1; }

mkdir -p "$OUT"

shot() {                       # shot <name> <path-and-query> [width] [height]
  local name="$1" route="$2" w="${3:-1440}" h="${4:-1180}"
  echo "  $name  <-  $route"
  # Three flags here are load-bearing, and all three were learned the hard way.
  #
  # --run-all-compositor-stages-before-draw: CSS animations do NOT advance with
  #   --virtual-time-budget, so without this the capture lands part-way through the
  #   `rise` entrance and the whole page comes out half-faded — which looks exactly like
  #   a contrast bug and is not one. Checking the DOM showed navy text at full opacity
  #   while the picture showed grey.
  # --force-prefers-reduced-motion: belt and braces on the same problem. The app already
  #   honours the preference, so the entrance becomes instant.
  # --force-device-scale-factor=2: the serif is a light-stroked face and at 1x it
  #   rasterises thin enough to read as washed out in a printed figure.
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --no-first-run --no-default-browser-check --disable-crash-reporter \
    --run-all-compositor-stages-before-draw \
    --force-prefers-reduced-motion \
    --force-device-scale-factor=2 \
    --user-data-dir="$PROFILE/$name" \
    --window-size="${w},${h}" --virtual-time-budget="${VTB:-12000}" \
    --screenshot="$OUT/${name}.png" "${BASE}${route}" 2>/dev/null || true
  [ -s "$OUT/${name}.png" ] || { echo "    FAILED — no image written" >&2; return 1; }
}

echo "Writing to $OUT"

# The landing page: one decision — start an account, or open a finished journal. The
# nine demonstration people moved inside the demo on 2026-11-20, so this no longer shows
# a list of strangers. First thing a grader sees, so it belongs in the report.
shot front-door "/" 1440 1180

# Catherine's two profiles. The same criterion carries a different tier in each, and
# "Soft hands" sits beside "Emotional maturity" without being ranked below it.
shot profiles-dark "/criteria?demo=thelonggame" 1440 1300

# Jane's patterns: a standard that quietly got easier, and a Mandatory criterion whose
# recorded decision has been "give it more time" three times.
shot patterns-dark "/patterns?demo=theintentionalist" 1440 1180

# Her progress view — counts and dates, never a score, and since 2026-11-20 the
# questions and suggestions waiting on her sit directly under the counts rather than on
# a separate Reflection tab. Taller than the others so the interactive part is in frame.
shot progress-dark "/progress?demo=theintentionalist" 1440 1500

# Journal History, which is where the agents' own reasoning is readable.
shot journal-dark "/journal?demo=thelonggame" 1440 1300

# Warm theme. Bianca's account is set to warm in the seed, so this needs no toggling —
# both palettes have to be shown and they come from one token set, not two stylesheets.
VTB=30000 shot patterns-warm "/patterns?demo=notyourtherapist" 1440 1180

rm -rf "$PROFILE"
echo
echo "Done:"
ls -la "$OUT"
