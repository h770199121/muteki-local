#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Content-type K sweep bench (codex P1: real-task K2/K3/K4 re-scan).

Same discipline as bench_llm.py (nonce, long output, greedy, drop first,
engine timings, median) but parameterized by CONTENT TYPE:
  en    — English technical repeat (matches the old sweep)
  code  — Python code block repeat (low token-entropy -> high acceptance)
  zh    — Chinese prose repeat (high token entropy -> low acceptance)
Usage: bench_ct.py <label> <url> <ctype> [max_tokens] [rounds]
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
CTYPE = sys.argv[3] if len(sys.argv) > 3 else "en"
MAX_TOKENS = int(sys.argv[4]) if len(sys.argv) > 4 else 700
ROUNDS = int(sys.argv[5]) if len(sys.argv) > 5 else 3
MODEL = os.environ.get("BENCH_MODEL", "qwen3.8-27b")
API_KEY = os.environ.get("BENCH_API_KEY", "")

CODE = (
    "def bench_kernel(grid, block, stream):\n"
    "    ctx = Context(grid=grid, block=block, stream=stream)\n"
    "    ctx.bind()\n"
    "    buf = alloc(4096, dtype='q8_0')\n"
    "    kernel = compile(SOURCE, arch='sm_75', sm_count=46)\n"
    "    for tile in tiles(buf, width=128):\n"
    "        kernel.launch(tile, ctx)\n"
    "    ctx.sync()\n"
    "    return buf.checksum()\n"
)
ZH = (
    "图形处理器通过大量并行线程来执行相同的指令流。在大语言模型推理过程中，"
    "内存带宽通常决定生成速度，而张量核心的吞吐决定提示处理的速度。量化后的权重矩阵"
    "必须先还原再与激活矩阵相乘。调度器根据本层看到的 token 数量选择内核档位。"
    "当上下文增长时，键值缓存随之增长，一旦溢出设备内存，每个 token 都要付出主机传输的代价。"
    "投机解码通过一次验证多个候选来提高每轮的输出数量。"
)


def make_prompt():
    nonce = uuid.uuid4().hex
    body = {"en": LONG_EN, "code": CODE, "zh": ZH}[CTYPE]
    return f"Session {nonce}. Repeat the following content verbatim with no changes:\n\n{body}"


LONG_EN = (
    "The graphics processing unit executes many threads in parallel. Each thread runs the same "
    "instruction stream on a different element of data. For large language model inference, memory "
    "bandwidth usually limits token generation, while tensor core throughput limits prompt processing. "
    "A quantized weight matrix must be unpacked before it is multiplied by the activation matrix. "
    "The scheduler decides which kernel rung to use based on how many tokens this layer sees. "
    "When the context grows, the key value cache grows with it, and once it spills out of device "
    "memory every token pays a host transfer cost. Speculative decoding raises the number of tokens "
    "emitted per round by drafting several candidates and verifying them in a single pass. "
) * 3


def check_url(url: str) -> None:
    p = urllib.parse.urlparse(url)
    if p.scheme != "http" or p.hostname not in ALLOWED_HOSTS:
        raise SystemExit("host not allowed (loopback-only bench)")


def call():
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": make_prompt()}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = "Bearer %s" % API_KEY
    req = urllib.request.Request(URL, data=payload, headers=headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data, time.perf_counter() - t0


def main():
    check_url(URL)
    print(f"### {LABEL} ctype={CTYPE} max_tokens={MAX_TOKENS} rounds={ROUNDS}")
    try:
        call()  # warmup dropped
    except Exception as exc:  # noqa: BLE001
        print(f"WARMUP FAILED: {exc!r}")
        return 1
    rows = []
    for i in range(ROUNDS):
        try:
            d, wall = call()
        except Exception as exc:  # noqa: BLE001
            print(f"ROUND {i+1} FAILED: {exc!r}")
            continue
        t = d.get("timings", {})
        rows.append({
            "decode_tps": round(t.get("predicted_per_second", 0), 1),
            "prefill_tps": round(t.get("prompt_per_second", 0), 1),
            "out_n": t.get("predicted_n"),
            "wall_s": round(wall, 2),
        })
        r = rows[-1]
        print(f"  round {i+1}: decode {r['decode_tps']} t/s | prefill {r['prefill_tps']} t/s | "
              f"out {r['out_n']} | wall {r['wall_s']}s")
    if not rows:
        print("NO VALID ROUNDS")
        return 1
    dec = [r["decode_tps"] for r in rows]
    pre = [r["prefill_tps"] for r in rows]
    print(f"--- MEDIAN decode={statistics.median(dec)} t/s  prefill={statistics.median(pre)} t/s ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
