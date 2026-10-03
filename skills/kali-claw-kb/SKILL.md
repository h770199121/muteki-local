---
name: kali-claw-kb
description: Distilled kali-claw security knowledge base (24 CTF domains). After triaging a challenge, route by category/symptom to ONE domain file under kb/ and read it before picking techniques or tools. Covers web (SQLi, XSS, SSRF, XXE, access control, auth bypass, deserialization, LFI, command injection, misconfig, DB, API), crypto, forensics/stego/pcap, binary RE/exploit dev, passwords/privesc/recon/network/payloads. Read at most 1-2 files per direction, then return to running commands on the target.
---

# kali-claw-kb — offline CTF knowledge and execution helpers

## Local tools before improvising shell commands

Run `python3 .agents/skills/kali-claw-kb/ctf_tools.py doctor` to discover actual
entrypoints. A listed path proves availability, not successful exploitation.
Ghidra headless and Volatility may use different paths than copied examples.

Search in Chinese or English:
`python3 .agents/skills/kali-claw-kb/kbsearch.py "登录 过滤 绕过" --domain web-sqli --json`
The output includes exact source lines and discloses relaxed matching. Read the
cited section and check prerequisites; a search result is not verified evidence.

For cookie/session/redirect handling or HTML-wrapped base64, read
`kb/tool-workflows.md` and use `ctf_tools.py http` / `decode`. These helpers use
Python's standard library, preserve raw artifacts and require no online install.
Operate only against the supplied local challenge. Missing offline dependencies
must be reported; do not fetch packages or call online services during a run.

Use: identify the challenge category or the concrete wall you hit → read the ONE
matching file below (Read tool) → apply its commands/payloads against the real
target. Do NOT read files speculatively; do not read more than two per direction.

| Domain | When to read | File |
|---|---|---|
| web-sqli | `SQL injection (error/union/blind/ooB, sqlmap, manual UNION)` | `kb/web-sqli.md` (+`kb/web-sqli-payloads.md` if present) |
| web-xss | `Cross-site scripting (reflected/stored/DOM, payloads, filters)` | `kb/web-xss.md` (+`kb/web-xss-payloads.md` if present) |
| web-ssrf | `Server-side request forgery (internal probing, cloud metadata, gopher)` | `kb/web-ssrf.md` (+`kb/web-ssrf-payloads.md` if present) |
| web-xxe | `XML external entity (file read, OOB exfil, blind XXE)` | `kb/web-xxe.md` (+`kb/web-xxe-payloads.md` if present) |
| web-access-control | `Broken access control / IDOR (horizontal & vertical authz)` | `kb/web-access-control.md` (+`kb/web-access-control-payloads.md` if present) |
| web-auth-bypass | `Auth bypass (JWT flaws, reset flows, session logic)` | `kb/web-auth-bypass.md` (+`kb/web-auth-bypass-payloads.md` if present) |
| web-deserialization | `Insecure deserialization (PHP/Java/Python gadget chains)` | `kb/web-deserialization.md` (+`kb/web-deserialization-payloads.md` if present) |
| file-inclusion | `LFI/RFI (traversal, wrappers, log poisoning, RCE)` | `kb/file-inclusion.md` (+`kb/file-inclusion-payloads.md` if present) |
| command-injection-advanced | `OS command injection (blind, evasion, shell tricks)` | `kb/command-injection-advanced.md` (+`kb/command-injection-advanced-payloads.md` if present) |
| security-misconfiguration | `Misconfig (default creds, exposed panels, debug endpoints)` | `kb/security-misconfiguration.md` (+`kb/security-misconfiguration-payloads.md` if present) |
| database-attack | `Database attacks (default creds, privesc, UDF, exfil)` | `kb/database-attack.md` (+`kb/database-attack-payloads.md` if present) |
| api-security | `API attacks (BOLA, mass assignment, hidden endpoints)` | `kb/api-security.md` (+`kb/api-security-payloads.md` if present) |
| crypto-attacks | `Classical & modern crypto attacks (RSA, AES, ECB, padding, hash)` | `kb/crypto-attacks.md` (+`kb/crypto-attacks-payloads.md` if present) |
| digital-forensics | `Digital forensics (file carving, memory, disk, pcap, exif)` | `kb/digital-forensics.md` (+`kb/digital-forensics-payloads.md` if present) |
| steganography | `Steganography (LSB, tools, audio/image/file carriers)` | `kb/steganography.md` (+`kb/steganography-payloads.md` if present) |
| network-sniffing-mitm | `Packet analysis & MITM (tcpdump/wireshark, protocol dissect)` | `kb/network-sniffing-mitm.md` (+`kb/network-sniffing-mitm-payloads.md` if present) |
| binary-reverse | `Binary reversing (static/dynamic, strings, decompile, anti-debug)` | `kb/binary-reverse.md` (+`kb/binary-reverse-payloads.md` if present) |
| reverse-engineering-advanced | `Advanced RE (obfuscation, VMs, patching, decompilers)` | `kb/reverse-engineering-advanced.md` (+`kb/reverse-engineering-advanced-payloads.md` if present) |
| exploit-development | `Exploit development (stack/heap, ROP, format string, shellcode)` | `kb/exploit-development.md` (+`kb/exploit-development-payloads.md` if present) |
| password-attack | `Password attacks (john/hashcat, wordlists, cracking modes)` | `kb/password-attack.md` (+`kb/password-attack-payloads.md` if present) |
| privilege-escalation | `Linux/Windows privilege escalation (SUID, sudo, kernel, services)` | `kb/privilege-escalation.md` (+`kb/privilege-escalation-payloads.md` if present) |
| recon-osint | `Recon & OSINT (nmap, subdomain, enum, open-source intel)` | `kb/recon-osint.md` (+`kb/recon-osint-payloads.md` if present) |
| network-pentest | `Network pentest (scanning, services, smb/ftp/ssh attacks)` | `kb/network-pentest.md` (+`kb/network-pentest-payloads.md` if present) |
| payload-generation | `Payload generation (revshells, encoders, obfuscation, helpers)` | `kb/payload-generation.md` (+`kb/payload-generation-payloads.md` if present) |
