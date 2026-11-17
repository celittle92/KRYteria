"""Pull Christine's own messages out of the session transcript, verbatim.

Read-only. Writes one file into this session's scratchpad so the prompt record can be
caught up from her actual words rather than from a summary of them.

Two record shapes carry what she typed, and the first version of this script only read
one of them:

* ``type: "user"`` with ``message.role == "user"`` — a message sent when it was her turn.
* ``type: "queue-operation", operation: "enqueue"`` with a plain-string ``content`` —
  a message she typed WHILE a turn was running, which the harness queued. Six of her
  messages, including the nine-item UI fix list, exist only in this shape.

Missing the second shape silently loses exactly the messages sent during long builds,
which is most of the interesting ones. Deduplicated on the text, earliest timestamp wins.
"""

import json
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
SINCE = sys.argv[3] if len(sys.argv) > 3 else "2026-11-12"


def text_of(msg):
    """Her typed words only — no tool results, no injected reminders."""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def keep(body: str) -> bool:
    if not body:
        return False
    if body.startswith("<system-reminder>") or body.startswith("Caveat:"):
        return False
    if body.startswith("<task-notification>"):
        return False
    if body.startswith("<local-command-stdout>"):
        return False
    return True


def main() -> int:
    seen = {}
    order = []
    with SRC.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            kind = rec.get("type")
            if kind == "queue-operation":
                if rec.get("operation") != "enqueue":
                    continue
                body = rec.get("content")
                body = body.strip() if isinstance(body, str) else ""
                tag = "queued"
            elif kind == "user":
                if rec.get("isMeta") or rec.get("isCompactSummary"):
                    continue
                msg = rec.get("message") or {}
                if msg.get("role") != "user":
                    continue
                body = text_of(msg).strip()
                tag = "sent"
            else:
                continue

            if not keep(body):
                continue
            ts = (rec.get("timestamp") or "")[:19]
            if ts and ts[:10] < SINCE:
                continue
            key = " ".join(body.split())
            if key in seen:
                continue
            seen[key] = True
            order.append((ts, tag, body))

    order.sort(key=lambda r: r[0])
    with OUT.open("w", encoding="utf-8") as fh:
        for ts, tag, body in order:
            fh.write("\n===== " + ts + "  [" + tag + "] =====\n")
            fh.write(body + "\n")
    print("wrote " + str(len(order)) + " messages to " + str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
