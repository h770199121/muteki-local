# Worker operating protocol (read this first — it exists because prior workers failed)

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
