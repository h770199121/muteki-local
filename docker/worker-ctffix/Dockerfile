# Derived worker image: closes the 3 MISSING tool gaps from the 2026-10-03
# Kali tool audit (docs/CTF增强实施方案-2026-10-03.md) — nuclei, zbarimg
# (zbar-tools), zsteg — and adds PATH entries for the two documented path
# issues: analyzeHeadless (lives at /usr/share/ghidra/support/) and vol3
# (Volatility entry is `vol`). Offline at runtime; packages are baked in here.
#
# Build:  docker build -t ghcr.io/fishcodetech/muteki-worker:zcode-ctf1 .
# Then point .env MUTEKI_WORKER_IMAGE at the new tag and recreate web-api.
FROM ghcr.io/fishcodetech/muteki-worker:zcode

USER root
RUN set -eux; \
    sed -i 's|http.kali.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list 2>/dev/null || true; \
    sed -i 's|http.kali.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/* 2>/dev/null || true; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nuclei zbar-tools; \
    gem sources --remove https://rubygems.org/ 2>/dev/null || true; \
    gem sources -a https://mirrors.tuna.tsinghua.edu.cn/rubygems/; \
    gem install zsteg --no-document; \
    ln -sf /usr/share/ghidra/support/analyzeHeadless /usr/local/bin/analyzeHeadless; \
    ln -sf /usr/local/bin/vol /usr/local/bin/vol3; \
    rm -rf /var/lib/apt/lists/*
# NOTE: keep the upstream default USER root. The runtime-agent ENTRYPOINT runs as
# this user and forks workers with a Credential{} drop to kali; starting it as
# kali makes Go's implicit setgroups() fail with EPERM → every StartWorker dies
# with "fork/exec /usr/bin/python3: operation not permitted" (run-20686).
