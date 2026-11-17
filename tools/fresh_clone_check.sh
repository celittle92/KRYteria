#!/bin/bash
# The dry run the assignment asks for, and the one row worth 5 points all-or-nothing.
#
#   "Clone the repo into a brand-new folder, put .env one level above, follow your own
#    README, and use the app. Not running after 10 minutes = 0 points."
#
# This reproduces the teaching staff's layout exactly:
#
#     <submissions>/
#       .env                 <- their key, one level ABOVE the repo
#       KRYteria/            <- the clone
#
# It does NOT copy anything from the working tree. It clones, so it tests what is
# actually committed — which is the whole point, and the way a stale dist/ or a missing
# file gets caught.
#
# Usage:  bash tools/fresh_clone_check.sh [git-url-or-path] [target-dir]
# Default clones this checkout, so you can test before pushing.

set -u

SOURCE="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
ROOT="${2:-${TMPDIR:-/tmp}/kryteria-freshclone-$(date +%H%M%S)}"
REPO="$ROOT/KRYteria"
FAILED=0

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
ok()   { printf '   \033[32mPASS\033[0m %s\n' "$1"; }
bad()  { printf '   \033[31mFAIL\033[0m %s\n' "$1"; FAILED=1; }

START=$(date +%s)

step "Fresh folder: $ROOT"
rm -rf "$ROOT"; mkdir -p "$ROOT"

step "The staff .env, one level above the repo"
# Names only. No value: the point is to prove the app LOOKS here, and demo mode needs
# no key at all, so a blank value still exercises the lookup without billing anything.
printf 'PORTKEY_API_KEY=\n' > "$ROOT/.env"
ok "wrote $ROOT/.env"

step "Clone"
if git clone --quiet "$SOURCE" "$REPO"; then ok "cloned from $SOURCE"; else bad "clone failed"; exit 1; fi

step "What a grader would NOT want to find in it"
for bad_path in .env .venv data/kryteria.db; do
  if [ -e "$REPO/$bad_path" ]; then bad "$bad_path is committed"; else ok "no $bad_path"; fi
done
[ -f "$REPO/README.md" ]      && ok "README.md present"      || bad "README.md missing"
[ -f "$REPO/.env.example" ]   && ok ".env.example present"   || bad ".env.example missing"
[ -d "$REPO/frontend/dist" ]  && ok "frontend/dist committed (no Node needed)" \
                              || bad "frontend/dist missing — the app would serve no UI"

step "Python, the way the README tells them to check it"
PY=python3
V=$("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo none)
case "$V" in
  3.1[2-9]|3.[2-9]*) ok "python3 is $V" ;;
  *) for c in python3.14 python3.13 python3.12; do
       command -v "$c" >/dev/null 2>&1 && { PY="$c"; ok "python3 is $V, using $c instead (as the README says)"; break; }
     done
     [ "$PY" = python3 ] && bad "no Python 3.12+ found — the README's fallback is Docker or the hosted link" ;;
esac

step "Install, exactly as the README says"
cd "$REPO" || exit 1
"$PY" -m venv .venv            || { bad "venv failed"; exit 1; }
if .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt; then
  ok "dependencies installed"
else
  bad "pip install failed"; exit 1
fi

step "Seed, exactly as the README says — both commands"
.venv/bin/python -m backend.seed_demo >/dev/null 2>&1       && ok "demo account"   || bad "seed_demo failed"
.venv/bin/python -m backend.seed_characters >/dev/null 2>&1 && ok "nine characters" || bad "seed_characters failed"

step "Does it actually come up, and is the front door populated?"
.venv/bin/python - <<'PROBE'
import sys
from fastapi.testclient import TestClient
from backend.main import app
c = TestClient(app)
fail = 0
def check(label, cond, extra=""):
    global fail
    print(("   \033[32mPASS\033[0m " if cond else "   \033[31mFAIL\033[0m ") + label + (" " + extra if extra else ""))
    if not cond: fail = 1

h = c.get("/api/health")
check("/api/health responds", h.status_code == 200)
j = h.json() if h.status_code == 200 else {}
check("it found the .env one level up", bool(j.get("env_source")), str(j.get("env_source")))
check("/ serves the front end", c.get("/").status_code == 200)

r = c.get("/api/demo/characters")
ch = r.json()
ch = ch.get("characters", ch) if isinstance(ch, dict) else ch
check("nine demo characters at the front door", isinstance(ch, list) and len(ch) == 9,
      "got %s" % (len(ch) if isinstance(ch, list) else ch))

if isinstance(ch, list) and ch:
    bad_signin = [x["handle"] for x in ch
                  if c.post("/api/auth/signin",
                            json={"handle": x["handle"],
                                  "passphrase": "kryteria-demo-" + x["handle"]}).status_code != 200]
    check("every character signs in", not bad_signin, str(bad_signin))

check("the demo account signs in", c.post("/api/auth/signin",
      json={"handle": "demo", "passphrase": "kryteria-demo-account"}).status_code == 200)
sys.exit(fail)
PROBE
[ $? -eq 0 ] || FAILED=1

ELAPSED=$(( $(date +%s) - START ))
step "Result"
printf '   %d seconds, against a 10-minute limit.\n' "$ELAPSED"
if [ "$FAILED" -eq 0 ]; then
  printf '   \033[32mA grader following the README gets a working app.\033[0m\n'
else
  printf '   \033[31mSomething above failed. Fix it before submitting.\033[0m\n'
fi
printf '   Clone left at %s — delete it when you are done.\n' "$REPO"
exit "$FAILED"
