#!/usr/bin/env python3
"""Download RedHatAI/Qwen3.8-27B-INT4 from ModelScope to a local dir."""
import sys
from modelscope import snapshot_download

dest = r"D:\AI\models-hf\Qwen3.8-27B-INT4"
p = snapshot_download(
    "RedHatAI/Qwen3.8-27B-INT4",
    local_dir=dest,
)
print("DONE:", p)
