#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standard benchmark for local llama.cpp/KVMem model lines (from the 3060
ninfer case's 测量夹具/bench.py, adapted):

  - fresh nonce in the prompt prefix -> forces a REAL prefill every request
    (otherwise the prefix cache collapses prompt_n and no prefill happens)
  - long prompt + long output (>=400 tokens); short outputs measure cold-start
    noise and fake low speculative acceptance
  - greedy (temperature 0)
  - drop the first request (weight swap-in / graph capture)
  - read the ENGINE's own timings (response.timings), not a client stopwatch
  - 3 rounds, report the MEDIAN

Only loopback/local-Docker hosts are allowed request targets (bench fixture,
never a general fetcher). Usage:
  bench_llm.py <label> [url] [max_tokens] [rounds]
  bench_llm.py swift-18202 http://127.0.0.1:18202/v1/chat/completions 700 3
"""
import json
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
import uuid

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "host.docker.internal"}

LABEL = sys.argv[1] if len(sys.argv) > 1 else "arm"
URL = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:18210/v1/chat/completions"
MAX_TOKENS = int(sys.argv[3]) if len(sys.argv) > 3 else 700
ROUNDS = int(sys.argv[4]) if len(sys.argv) > 4 else 3
MULT = int(sys.argv[5]) if len(sys.argv) > 5 else 8
MODEL = os.environ.get("BENCH_MODEL", "qwen3.8-27b")
API_KEY = os.environ.get("BENCH_API_KEY", "")

PARA = (
    "The graphics processing unit executes many threads in parallel. Each thread runs the same "
    "instruction stream on a different element of data. For large language model inference, memory "
    "bandwidth usually limits token generation, while tensor core throughput limits prompt processing. "
    "A quantized weight matrix must be unpacked before it is multiplied by the activation matrix. "
    "The scheduler decides which kernel rung to use based on how many tokens this layer sees. "
    "When the context grows, the key value cache grows with it, and once it spills out of device "
    "memory every token pays a host transfer cost. Speculative decoding raises the number of tokens "
    "emitted per round by drafting several candidates and verifying them in a single pass. "
)
LONG_PROMPT = " ".join([PARA] * MULT)


def check_url(url: str) -> None:
    p = urllib.parse.urlparse(url)
    if p.scheme != "http":
        raise SystemExit("only http is allowed: %r" % url)
    if p.hostname not in ALLOWED_HOSTS:
        raise SystemExit("host not allowed (loopback-only bench): %r" % p.hostname)


def make_prompt():
    return (
        "Session %s. Repeat the following text verbatim, word for word, "
        "with no additions and no omissions:\n\n%s" % (uuid.uuid4().hex, LONG_PROMPT)
    )


def call():
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": make_prompt()}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = "Bearer %s" % API_KEY
    req = urllib.request.Request(URL, data=body, headers=headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data, time.perf_counter() - t0


def main():
    check_url(URL)
    print("### arm=%s  model=%s  max_tokens=%d  rounds=%d" % (LABEL, MODEL, MAX_TOKENS, ROUNDS))
    print("### warmup (dropped)...")
    try:
        call()
    except Exception as exc:  # noqa: BLE001
        print("WARMUP FAILED: %r" % (exc,))
        return 1

    rows = []
    for i in range(ROUNDS):
        try:
            d, wall = call()
        except Exception as exc:  # noqa: BLE001
            print("ROUND %d FAILED: %r" % (i + 1, exc))
            continue
        t = d.get("timings", {})
        rows.append({
            "round": i + 1,
            "wall_s": round(wall, 2),
            "prompt_n": t.get("prompt_n"),
            "out_n": t.get("predicted_n"),
            "prefill_tps": round(t.get("prompt_per_second", 0), 1),
            "decode_tps": round(t.get("predicted_per_second", 0), 1),
            "ms_per_token": round(t.get("predicted_per_token_ms", 0), 2),
            "ttft_ms": round(t.get("prompt_ms", 0), 0),
            "finish": d.get("choices", [{}])[0].get("finish_reason"),
        })
        r = rows[-1]
        print("  round %d: prompt %s tok | out %s tok | prefill %s t/s | decode %s t/s | "
              "%.2f ms/tok | ttft %s ms | wall %.2fs | finish=%s"
              % (r["round"], r["prompt_n"], r["out_n"], r["prefill_tps"], r["decode_tps"],
                 r["ms_per_token"], r["ttft_ms"], r["wall_s"], r["finish"]))

    if not rows:
        print("NO VALID ROUNDS")
        return 1
    dec = [r["decode_tps"] for r in rows]
    pre = [r["prefill_tps"] for r in rows]
    print("--- MEDIAN ---")
    print("  decode  = %.1f t/s   (samples: %s)" % (statistics.median(dec), dec))
    print("  prefill = %.1f t/s   (samples: %s)" % (statistics.median(pre), pre))
    return 0


if __name__ == "__main__":
    sys.exit(main())
