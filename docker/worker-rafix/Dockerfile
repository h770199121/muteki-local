# Derived worker image (build context = REPO ROOT):
#   docker build -t ghcr.io/fishcodetech/muteki-worker:zcode-ctf3 \
#     -f docker/worker-rafix/Dockerfile .
# Deploy: .env MUTEKI_WORKER_IMAGE=ghcr.io/fishcodetech/muteki-worker:zcode-ctf3
#         + recreate web-api. Rollback = restore .env line.
#
# Purpose: sync ALL repo-owned baked files over the stale 2026-09-12 hand-built
# `:zcode` base (the ctf1/ctf2/ctf3 line derives from it, so every baked file
# was 9-12 era until overlayed here):
#   1. runtime_agent — current build (deployed binary predates the
#      drain-before-reap stdout ordering fix in cmd/runtime-agent/worker.go).
#   2. deepseek_harness_worker.py — parallel tool-call turns arrive as ONE
#      message with N tool-result blocks; the old next() emitted only the
#      first block, dropping every other result (and any flag inside it).
#   3. AGENTS.md / CLAUDE.md — canonical worker prompt (docker/worker/AGENTS.md,
#      the proven live P0-2 action-card content), synced over the 9-12 seed.
#   4. muteki-blackboard skill + script, offline_acp_bridge.py,
#      omp_offline_config.yml, kimi/grok offline agents — same 9-12 staleness.
#      The live blackboard skill is projected from the web-api repo copy, so
#      these are fallback-path hygiene.
# Single source rule: docker/worker/AGENTS.md == worker_skills staging source.
# After changing any baked file: rebuild this image (same tag is fine — worker
# containers are per-run and resolve the tag at launch) and rebuild the web-api
# image so its repo copies stay in lockstep.
FROM ghcr.io/fishcodetech/muteki-worker:zcode-ctf1
COPY docker/worker-rafix/runtime_agent-amd64 /opt/muteki/runtime_agent
COPY muteki/solver/deepseek_harness_worker.py /opt/muteki/deepseek_harness_worker.py
COPY docker/worker/AGENTS.md /opt/muteki/AGENTS.md
COPY docker/worker/AGENTS.md /opt/muteki/CLAUDE.md
COPY skills/muteki-blackboard/SKILL.md /opt/muteki/muteki-blackboard/SKILL.md
COPY skills/muteki-blackboard/blackboard.py /opt/muteki/muteki-blackboard/blackboard.py
COPY skills/muteki-blackboard/blackboard.py /usr/local/bin/blackboard.py
COPY muteki/solver/offline_acp_bridge.py /opt/muteki/offline_acp_bridge.py
COPY muteki/solver/omp_offline_config.yml /opt/muteki/omp_offline_config.yml
COPY muteki/solver/kimi_offline_agent.md /opt/muteki/kimi_offline_agent.md
COPY muteki/solver/grok_offline_agent.md /opt/muteki/grok_offline_agent.md
RUN chmod +x /opt/muteki/runtime_agent /opt/muteki/muteki-blackboard/blackboard.py \
    /usr/local/bin/blackboard.py
