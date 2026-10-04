"""Switch the local model line (A=8888 / B=18200 / C=8890) for the muteki stack.

Updates (all paths are fixed constants inside this project):
  - data/sessions/_worker_config.json  (planner/titler llm_profiles + dsh seat models)
  - data/sessions/_secrets/accounts/dsh-local/BASE_URL
  - data/sessions/_secrets/accounts/zcode-local-qwen/zcode-home/.zcode/cli/config.json

Usage:
  uv run --no-project python labs/nyu-ctf/switch_line.py --line B
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(r"D:\AI\muteki-local").resolve()
WORKER_CONFIG = ROOT / "data" / "sessions" / "_worker_config.json"
DSH_BASE_URL_FILE = ROOT / "data" / "sessions" / "_secrets" / "accounts" / "dsh-local" / "BASE_URL"
ZCODE_CONFIG = (
    ROOT / "data" / "sessions" / "_secrets" / "accounts" /
    "zcode-local-qwen" / "zcode-home" / ".zcode" / "cli" / "config.json"
)

# Lines served by a gateway that still requires a bearer token. The value lives in
# MUTEKI_DEEPSEEK_API_KEY (see .env / the environment) and is never written to
# source, so this file carries no credential.
REMOTE_KEY = os.environ.get("MUTEKI_DEEPSEEK_API_KEY", "").strip() or "local-no-key"

LINES = {
    "A": {"base": "http://host.docker.internal:8888/v1", "model": "qwen3.8-27b",
          "key": REMOTE_KEY},
    "B": {"base": "http://host.docker.internal:18200/v1", "model": "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
          "key": "local-no-key"},
    "X1": {"base": "http://host.docker.internal:18202/v1", "model": "qwen38-iq3xxs",
           "key": "local-no-key"},
    "X2": {"base": "http://host.docker.internal:18202/v1", "model": "swift15-iq3xxs",
           "key": "local-no-key"},
    "X3": {"base": "http://host.docker.internal:18202/v1", "model": "signal38-iq3xxs",
           "key": "local-no-key"},
    "X2D": {"base": "http://host.docker.internal:18212/v1", "model": "swift15-iq3xxs",
            "key": "local-no-key"},
    "BM": {"base": "http://host.docker.internal:18202/v1", "model": "base-mtp-iq3xxs",
           "key": "local-no-key"},
    "BM2": {"base": "http://host.docker.internal:18215/v1", "model": "base-mtp-iq3xxs",
            "key": "local-no-key"},
    "FULL": {"base": "http://host.docker.internal:18210/v1", "model": "qwen3.8-27b",
             "key": REMOTE_KEY},
    "C": {"base": "http://host.docker.internal:8890/v1", "model": "occamy-1.0",
          "key": REMOTE_KEY},
    # Occamy dual on the standard llama.cpp launcher (both start.bat menus,
    # option 3): 19.7 GiB weights → dual only, listens on 18214. Batch-4-1:
    # the menus referenced this line without it existing, so a failed switch
    # silently left the swarm on the previous model line.
    "X4": {"base": "http://host.docker.internal:18214/v1", "model": "occamy-1.0",
           "key": "local-no-key"},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--line", required=True, choices=sorted(LINES))
    args = ap.parse_args()
    ln = LINES[args.line]

    cfg = json.loads(WORKER_CONFIG.read_text(encoding="utf-8"))
    for prof in ("planner", "titler"):
        lp = cfg.setdefault("llm_profiles", {}).setdefault(prof, {})
        lp["base_url"] = ln["base"]
        lp["model"] = ln["model"]
        lp["temperature_mode"] = "omit"
    for p in cfg.get("worker_profiles", []):
        if p.get("engine") == "dsh":
            p["base_url"] = ln["base"]
            p["model"] = ln["model"]
        if p.get("engine") == "zcode":
            p["model"] = ""
    for s in cfg.get("seats", []):
        if s.get("engine") == "dsh":
            s["model"] = ln["model"]
        if s.get("engine") == "zcode":
            s["model"] = ""
    WORKER_CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    DSH_BASE_URL_FILE.write_text(ln["base"] + "\n", encoding="utf-8")

    zc = json.loads(ZCODE_CONFIG.read_text(encoding="utf-8"))
    provider = zc.setdefault("provider", {}).setdefault("qwen-local", {})
    provider["kind"] = "anthropic"
    provider.setdefault("options", {})["baseURL"] = ln["base"].removesuffix("/v1")
    provider["options"]["apiKey"] = ln["key"]
    zc.setdefault("model", {})["main"] = f"qwen-local/{ln['model']}"
    ZCODE_CONFIG.write_text(json.dumps(zc, separators=(",", ":")), encoding="utf-8")

    print(f"switched to line {args.line}: {ln['base']} model={ln['model']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
