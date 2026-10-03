"""Worker-scoped skill projection.

Muteki must never install its coordination skill into an operator's user-level
agent configuration.  Every CLI already supports project-local skills, so each
Worker gets a private projection under its own cwd.  User skills remain visible
through the engine's normal user-level discovery and disappear from the Muteki
projection when the Worker workspace is removed.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


_REPO_SKILL = (
    Path(__file__).resolve().parents[2] / "skills" / "muteki-blackboard"
)

# `.agents/skills` is the common Agent Skills location used by Codex, Pi and
# recent compatible CLIs.  Engine-specific locations keep discovery deterministic
# for tools that do not scan the common directory.
_PROJECT_SKILL_ROOTS: dict[str, tuple[str, ...]] = {
    "claude": (".claude/skills", ".agents/skills"),
    "codex": (".agents/skills", ".codex/skills"),
    "cursor": (".cursor/skills", ".agents/skills"),
    "pi": (".pi/skills", ".agents/skills"),
    "omp": (".omp/skills", ".agents/skills"),
    "kimi": (".kimi/skills", ".agents/skills"),
    "grok": (".grok/skills", ".agents/skills"),
    "opencode": (".opencode/skills", ".agents/skills"),
    "dsh": (".agents/skills",),
    "zcode": (".zcode/skills", ".agents/skills"),
}


def project_skill_roots(engine: str) -> tuple[str, ...]:
    return _PROJECT_SKILL_ROOTS.get(
        str(engine or "").strip().lower(), (".agents/skills",)
    )


def stage_blackboard_skill(
    workdir: str | Path,
    *,
    engine: str,
    container: bool = False,
) -> list[str]:
    """Expose ``muteki-blackboard`` only inside one Worker's cwd.

    Local Workers receive symlinks to the repository copy.  Container Workers
    receive links to the immutable image copy because the host repository path is
    not mounted inside the Worker container.  A pre-existing non-symlink path is
    preserved; Muteki never overwrites project content supplied by the operator.
    """

    root = Path(workdir).resolve()
    target = Path("/opt/muteki/muteki-blackboard") if container else _REPO_SKILL
    if not container and not target.is_dir():
        raise FileNotFoundError(f"muteki-blackboard skill source missing: {target}")

    staged: list[str] = []
    for relative in project_skill_roots(engine):
        skills_root = root / relative
        dest = skills_root / "muteki-blackboard"
        skills_root.mkdir(parents=True, exist_ok=True)
        try:
            if dest.is_symlink():
                if os.readlink(dest) == str(target):
                    staged.append(str(dest))
                    continue
                dest.unlink()
            elif dest.exists():
                # A Worker attachment/project may intentionally provide a skill
                # with this name.  Keep it intact and rely on the explicit script
                # path for the protocol implementation.
                staged.append(str(dest))
                continue
            dest.symlink_to(target, target_is_directory=True)
        except OSError:
            # Filesystems without symlink support get a private physical copy for
            # local execution.  The container path is not readable on the host, so
            # that case must fail loudly instead of copying an unrelated source.
            if container:
                raise
            shutil.copytree(target, dest)
        staged.append(str(dest))
    return staged


def stage_extra_skills(
    workdir: str | Path,
    *,
    engine: str,
    container: bool = False,
) -> list[str]:
    """Stage optional operator-provided skills into one Worker's project roots.

    ``MUTEKI_EXTRA_SKILLS_DIR`` points at a directory whose immediate
    subdirectories are skill folders (SKILL.md format). Each subdirectory is
    COPIED into every project skill root of the Worker cwd — copies, not links,
    so they resolve identically for local and container Workers regardless of
    bind-mount semantics. Existing content is never overwritten (same policy as
    the blackboard staging). A missing/unreadable source silently stages nothing:
    extra skills are an operator convenience, never a launch blocker.
    """

    src_root = os.environ.get("MUTEKI_EXTRA_SKILLS_DIR", "").strip()
    if not src_root:
        return []
    base = Path(src_root)
    try:
        candidates = sorted(p for p in base.iterdir() if p.is_dir())
    except OSError:
        return []

    root = Path(workdir).resolve()
    staged: list[str] = []
    for relative in project_skill_roots(engine):
        skills_root = root / relative
        for src in candidates:
            dest = skills_root / src.name
            if dest.exists():
                staged.append(str(dest))
                continue
            skills_root.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copytree(src, dest)
                staged.append(str(dest))
            except OSError:
                continue
    if staged:
        _write_kb_pointer(root)
    return staged


_KB_POINTER = """# Worker operating protocol (read this first — it exists because prior workers failed)

## 0. Mandatory at start and after every fruitless worker
Run: `python3 "$MUTEKI_BLACKBOARD_SCRIPT" read-directives`
If a coordinator REFLECTION directive is present, follow it exactly — it encodes
what the previous worker already ruled out. Also run `read-facts` + `read-deadends`
and NEVER repeat a payload on the dead-end list.

## 1. Symptom → mandatory action (stop guessing, do the named action)
- **Login form resists ≥5 credential guesses** → STOP guessing. Run the 4-step
  filter-reverse protocol in `.agents/skills/kali-claw-kb/kb/web-sqli.md`
  (section "Login Auth Bypass + Keyword-Filter Reverse Engineering"): try
  `admin'--`, diff echoed vs sent input, test keyword nesting (`adadminmin`).
- **A probe fails silently or with a syntax error** → print
  `FAILED_PROBE=<input>|<difference>` and DIFF the echo. A target that mangles
  your input reveals its filter for free.
- **Same response for 3 different payloads** → your requests are not reaching
  the code path you think; re-read the form/JS and vary the parameter NAME,
  not just the value.
- **Directory brute-force comes up empty** → check response headers, error-page
  fingerprints and default app paths first (see kb/security-misconfiguration.md).
- **File upload / inclusion / RCE wall** → kb/file-inclusion.md,
  kb/command-injection-advanced.md, kb/web-deserialization.md.
- **Crypto / forensics / stego / pcap** → kb/crypto-attacks.md,
  kb/digital-forensics.md, kb/steganography.md, kb/network-sniffing-mitm.md.
- **Binary / pwn** → kb/binary-reverse.md, kb/exploit-development.md.

## 2. Knowledge base search (use it — one command, instant answer)
`python3 .agents/skills/kali-claw-kb/kbsearch.py "<symptom or technique words>"`
Returns the most relevant KB sections with file+line pointers. Full routing
index: `.agents/skills/kali-claw-kb/SKILL.md`. Search BEFORE inventing a
technique from scratch; read at most 1-2 files per direction.
"""


def _write_kb_pointer(root: Path) -> None:
    """Drop an AGENTS.md pointer into the worker cwd (never overwrite)."""
    dest = root / "AGENTS.md"
    if dest.exists():
        return
    try:
        dest.write_text(_KB_POINTER, encoding="utf-8")
    except OSError:
        pass


def legacy_user_skill_paths(home: str | Path | None = None) -> tuple[Path, ...]:
    """Known user-level locations used by older Muteki releases."""

    base = Path(home).expanduser() if home is not None else Path.home()
    return (
        base / ".claude/skills/muteki-blackboard",
        base / ".agents/skills/muteki-blackboard",
        base / ".codex/skills/muteki-blackboard",
        base / ".cursor/skills-cursor/muteki-blackboard",
        base / ".cursor/skills/muteki-blackboard",
        base / ".pi/agent/skills/muteki-blackboard",
        base / ".omp/agent/skills/muteki-blackboard",
        base / ".kimi-code/skills/muteki-blackboard",
        base / ".grok/skills/muteki-blackboard",
    )
