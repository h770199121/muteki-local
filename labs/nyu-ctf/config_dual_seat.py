"""Add a second dsh seat (Signal @18203) to _worker_config.json for dual-GPU swarm.

Idempotent: skips if the signal seat already exists. Keeps the Swift seat as
baseline. Sets max_workers=2 / start_workers=2 so both engines run in parallel.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\AI\muteki-local").resolve()
WC = ROOT / "data" / "sessions" / "_worker_config.json"

SWIFT_BASE = "http://host.docker.internal:18202/v1"
SWIFT_MODEL = "swift15-iq3xxs"
SIGNAL_BASE = "http://host.docker.internal:18203/v1"
SIGNAL_MODEL = "signal38-iq3xxs"

cfg = json.loads(WC.read_text(encoding="utf-8"))

seat_ids = {s.get("id") for s in cfg.get("seats", [])}
prof_ids = {p.get("id") for p in cfg.get("worker_profiles", [])}

if "dsh-signal-local" not in prof_ids:
    cfg.setdefault("worker_profiles", []).append({
        "id": "dsh-signal-local", "name": "dsh-signal-local",
        "label": "DSH Signal @18203 (T10)",
        "engine": "dsh", "transport": "dsh_sdk_worker",
        "credential_mode": "api_key", "auth": "api_key",
        "credential_account": "dsh-local-signal",
        "api_key_ref": "",
        "base_url": SIGNAL_BASE, "model": SIGNAL_MODEL,
        "wire_api": "chat_completions",
        "roles": ["race", "bootstrap", "explore", "respond", "review", "verifier"],
        "race": False, "max_running": 1, "max_review_running": 0,
        "max_verifier_running": 0, "priority": 30,
        "reasoning_effort": "default", "enabled": True,
    })
if "seat_dsh_signal" not in seat_ids:
    cfg.setdefault("seats", []).append({
        "id": "seat_dsh_signal", "label": "DSH Signal @18203 (T10)",
        "engine": "dsh", "credential_id": "cred_dsh_signal",
        "model": SIGNAL_MODEL, "reasoning_effort": "default",
        "roles": ["race", "bootstrap", "explore", "respond", "review", "verifier"],
        "race": False,
        "capacity": {"max_running": 1, "max_review_running": 0},
        "priority": 30, "enabled": True,
    })
cred_ids = {c.get("id") for c in cfg.get("credentials", [])}
if "cred_dsh_signal" not in cred_ids:
    cfg.setdefault("credentials", []).append({
        "id": "cred_dsh_signal", "label": "dsh-signal-local",
        "engine": "dsh", "kind": "custom_endpoint",
        "secret_ref": "dsh-local-signal",
        "endpoint": {"base_url": SIGNAL_BASE, "wire_api": "chat_completions"},
        "target_engine": "dsh",
    })

cfg["max_workers"] = 2
cfg["start_workers"] = 2

# planner/titler stay on the Swift baseline endpoint
for prof in ("planner", "titler"):
    lp = cfg.setdefault("llm_profiles", {}).setdefault(prof, {})
    lp["base_url"] = SWIFT_BASE
    lp["model"] = SWIFT_MODEL
    lp["temperature_mode"] = "omit"

WC.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
print("dual-seat config written:")
for s in cfg.get("seats", []):
    print("  seat:", s.get("id"), s.get("engine"), s.get("model"), s.get("priority"))
print("  max_workers:", cfg["max_workers"], "| start_workers:", cfg["start_workers"])
