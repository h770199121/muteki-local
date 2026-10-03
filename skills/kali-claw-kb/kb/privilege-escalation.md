# privilege-escalation

# Skill: Privilege Escalation

> **Supplementary Files**:
> - `payloads.md` — Complete command reference organized by escalation vector: automated enumeration, SUID/GTFOBins exploitation, sudo abuse, capabilities, kernel exploits, Windows token impersonation, service path hijacking, DLL hijacking, and UAC bypass
> - `test-cases.md` — Structured test case templates (TC-PE-001 to TC-PE-008) covering Linux and Windows privilege escalation scenarios with severity ratings and expected results

## Summary

Privilege Escalation skill domain covering post exploitation operations.

**Tools**: linpeas, winpeas, linux-exploit-suggester, pspy, GTFOBins, lolbas, sudo, capsh

**Domain**: post-exploitation

**MITRE ATT&CK**: TA0004-Privilege Escalation

## Description

Privilege escalation is the process of elevating access from a low-privileged user context (standard user, service account, or limited shell) to root on Linux or SYSTEM/Administrator on Windows. It is the critical bridge between initial foothold and full system control, determining the depth and impact of a penetration test or red team engagement.

This skill covers the complete escalation workflow: automated enumeration with linpeas/winpeas, manual verification of misconfigurations, exploitation of SUID binaries via GTFOBins, sudo rule abuse, Linux capabilities exploitation, cron job hijacking, kernel exploit identification and safe execution, and Windows-specific vectors including token impersonation, unquoted service paths, DLL hijacking, AlwaysInstallElevated, and UAC bypass techniques.

Core objective: systematically identify and exploit every viable escalation path from the current user context to the highest privilege level on the target system.

---

## Use Cases

1. **Low-privilege shell on Linux** — Escalate from a www-data or standard user shell to root via SUID binaries, sudo misconfigurations, cron abuse, or kernel exploits
2. **Low-privilege shell on Windows** — Escalate from a standard user to SYSTEM or Administrator via token impersonation, service misconfigurations, or UAC bypass
3. **Container escape context** — Identify capabilities, SUID binaries, or host-mounted filesystems that enable breakout from a container to the host
4. **Domain environment escalation** — Leverage local privilege escalation as a stepping stone to domain-level compromise through credential harvesting and lateral movement
5. **Red team assessment depth** — Demonstrate the full impact of an initial compromise by reaching the highest privilege level, proving that the foothold leads to complete system control

---

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **linpeas** | Automated Linux privilege escalation enumeration; checks SUID, sudo, capabilities, cron, NFS, kernel, and hundreds of misconfiguration vectors | `./linpeas.sh -a 2>/dev/null \| tee linpeas.out` |
| **winpeas** | Automated Windows privilege escalation enumeration; checks services, tokens, registry, UAC, stored credentials, and DLL hijacking paths | `.\winPEAS.exe quiet cmd fast` |
| **linux-exploit-suggester** | Kernel version-based exploit recommendation; maps running kernel to known CVEs with reliability ratings | `./linux-exploit-suggester.sh --uname "5.4.0"` |
| **pspy** | Monitor running processes without root; discover cron jobs, scheduled tasks, and hidden root processes in real time | `./pspy64 -pf -i 1000` |
| **GTFOBins** | Reference database of Unix binaries exploitable for privilege escalation through SUID, sudo, or capabilities | Reference: https://gtfobins.github.io |
| **lolbas** | Reference database of Windows living-off-the-land binaries usable for escalation, execution, or credential access | Reference: https://lolbas-project.github.io |
| **sudo** | Exploit sudo misconfigurations: NOPASSWD entries, wildcard injection, env_keep, and rule-based bypasses | `sudo -l; sudo /usr/bin/vim -c ':!/bin/bash'` |
| **capsh** | Enumerate and decode Linux capabilities on binaries; identify exploitable capability assignments | `capsh --print; getcap -r / 2>/dev/null` |

---

## Methodology

### Attack Chain

```
Enumeration                    Identification                 Exploitation
(linpeas, winpeas,           (sudo -l, SUID find,           (GTFOBins, kernel exploit,
 manual checks)               getcap, pspy)                  token impersonation)
      |                              |                              |
      v                              v                              v
                           Escalation                    Persistence & Documentation
                           (root/SYSTEM shell)           (document path, clean artifacts)
```

**Phase details**:

1. **Enumerate** — Run linpeas (Linux) or winpeas (Windows) for automated enumeration. Collect system information: kernel version, OS release, running processes, installed packages, network configuration, and user context. This phase casts the widest possible net to identify all potential escalation vectors.

2. **Identify** — Manually verify and prioritize the enumeration findings. Check sudo permissions (`sudo -l`), locate SUID binaries (`find / -perm -4000`), enumerate capabilities (`getcap -r /`), inspect cron jobs (`/etc/crontab`, `crontab -l`), and review running services. On Windows, examine token privileges (`whoami /priv`), service configurations, registry keys, and UAC settings. Prioritize vectors by reliability and impact.

3. **Exploit** — Apply the appropriate exploitation technique for the identified vector. Use GTFOBins for SUID/sudo binary exploitation, linux-exploit-suggester output for kernel-level attacks, token impersonation for Windows privilege abuse, or lolbas techniques for living-off-the-land escalation. Execute with caution, especially for kernel exploits which can destabilize the target.

4. **Escalate** — Achieve root (Linux) or SYSTEM/Administrator (Windows) access through the exploited vector. Verify the escalation with `id` or `whoami` commands. Harvest credentials from the elevated context for further lateral movement if within scope.

5. **Persist** — Document the complete escalation path including every command executed, every file modified, and every vulnerability exploited. Record the before/after privilege context. Clean up any artifacts (uploaded tools, temporary files) unless persistence testing is explicitly authorized.

## Practical Steps

### Linux Escalation Workflow

1. Run `linpeas.sh -a` for automated enumeration
2. Check `sudo -l` for misconfigured rules
3. Run `find / -perm -4000 -type f 2>/dev/null` for SUID binaries
4. Run `getcap -r / 2>/dev/null` for capabilities
5. Inspect `/etc/crontab` and `crontab -l` for cron abuse
6. Check `cat /proc/version; uname -r` for kernel exploits
7. Run `linux-exploit-suggester.sh` to map kernel CVEs
8. Verify with `pspy64` for hidden scheduled processes
9. Exploit highest-reliability vector first
10. Confirm with `id` showing uid=0(root)

### Windows Escalation Workflow

1. Run `winPEAS.exe quiet cmd fast` for automated enumeration
2. Check `whoami /priv` for exploitable token privileges
3. Run `systeminfo` for OS version and patch level
4. Check `net user; net localgroup administrators` for user context
5. Inspect `sc qc <service>` for unquoted service paths
6. Check registry for AlwaysInstallElevated and stored credentials
7. Run `accesschk.exe` for writable service directories
8. Exploit token impersonation if SeImpersonatePrivilege present
9. Attempt UAC bypass if standard user can auto-elevate
10. Confirm with `whoami` showing SYSTEM or Administrator

---

## Defense Evasion Techniques

### Stealth Enumeration
- **Slow scanning**: Space enumeration across hours; cache results to avoid repeated `find` calls.
- **LOLBins over custom tools**: Use `getent`, `id`, `groups`, `ls -la /etc/sudoers` instead of dropping `linpeas`.
- **Native binary renaming**: Copy `find` to `~/.local/bin/.cache` to avoid process-name detection.
- **PowerShell without AMSI**: Patch `amsi.dll` in-memory before enumeration; use `pwsh` CoreCLR bypass.
- **In-memory enumeration**: Use `Reflective PE` loading or `.NET Interactive` to run tools without disk artifacts.

### Service Exploitation Stealth
- **Service binary obfuscation**: Encode service binary with custom encoder to evade AV signatures.
- **DLL hijacking over custom binary**: Use legitimate signed binary + malicious DLL sidecar (less suspicious than dropping .exe).
- **WMI over PsExec**: Use WMI subscription (`__EventFilter` + `CommandLineEventConsumer`) instead of `PsExec` to avoid `PSEXESVC.exe` service creation event.
- **DCOM over RPC**: Use DCOM (`MMC20.Application`) for lateral movement to avoid standard RPC patterns.

### Token Impersonation Stealth
- **Stolen token over delegation**: Use stolen token to access services instead of creating new logon events.
- **Process injection into legit process**: Inject into `explorer.exe` or `svchost.exe` to inherit legitimate token.
- **Avoid `whoami /priv`**: Use `OpenProcessToken` + `GetTokenInformation` API directly to avoid SIEM-detected `whoami` invocation.

### Kernel Exploit Stealth
- **Target isolated hosts**: Run kernel exploits on isolated hosts to avoid panic-induced reboots visible to monitoring.
- **Match kernel version precisely**: Avoid partial-match exploitation (crashes); use `uname -r` exact match.
- **Memory-only exploits**: Prefer in-memory kernel exploits (no `/tmp/exploit` artifacts).
- **Use known-good variants**: `DirtyPipe` (CVE-2022-0847) over `DirtyCOW` (CVE-2016-5195) — newer, less signatured.

### Log Manipulation
- **Selective clearing**: Delete only specific audit logs (`/var/log/audit/audit.log` lines for our session) instead of full file.
- **Time-stomping**: Modify file timestamps with `timestomp` (Meterpreter) to match legitimate binaries.
- **Auditd rule abuse**: Pause auditd rules via `auditctl -e 0` if root; restore after operations.
- **Hide processes**: Use rootkit-style `LD_PRELOAD` hook to hide our processes from `ps`.

### Container Escape Stealth
- **Sidecar injection over new container**: Inject into existing pod rather than spawning new container (visible to kubectl get pods).
- **Bypass via mounted Docker socket**: Use `/var/run/docker.sock` mount to spawn sibling container (less visible than escape).
- **kubelet over API server**: Use kubelet API on worker node (`10250`) to escape API server monitoring.
- **eBPF bypass**: Some kernel exploits don't trigger eBPF-based Falco rules (e.g., `CVE-2022-0185` before Falco rule update).

---
