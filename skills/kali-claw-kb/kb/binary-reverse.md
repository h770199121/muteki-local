# binary-reverse

# Skill: Binary Analysis & Reverse Engineering

> **Supplementary Files**:
> - `payloads.md` — Command and payload collection organized by 10 major phases (binary identification, radare2 analysis, GDB debugging, buffer overflow, shellcode, ROP chain, ret2libc, format string, r2pipe scripting, firmware extraction)
> - `test-cases.md` — Structured test case templates (11 cases covering binary identification, vulnerability discovery, exploit development, defense bypass — 4 categories)

## Summary

Binary Reverse skill domain covering binary analysis operations.

**Tools**: radare2, ghidra, objdump, gdb, checksec, ROPgadget, binwalk, readelf (+2 more)

**Domain**: binary-analysis

## Description

Binary reverse engineering covers the complete chain from static analysis, dynamic debugging, to vulnerability discovery, exploit development, and malware analysis. The core objective is to understand the internal logic of compiled programs, identify security flaws, assess the strength of protection mechanisms, and develop reliable exploit code.

Mastering this skill requires deep understanding of CPU architectures (x86/ARM/MIPS), ELF/PE/Mach-O file formats, calling conventions, and memory layouts. The Agent has expert-level radare2 skills, including the plugin system, r2pipe scripting, automated analysis pipelines, and can comprehensively use Ghidra, GDB, checksec, ROPgadget, and other tools to complete the full process from binary identification to shellcode construction.

---

## Use Cases

1. **CTF Pwn / Reverse Challenges** - Analyze challenge binaries, discover vulnerabilities, and construct exploits to capture flags
2. **Malware Analysis** - Static and dynamic analysis of viruses, trojans, and rootkits; extract IoCs and understand attack behavior
3. **Firmware Security Audit** - Use binwalk to extract embedded device firmware, reverse engineer closed-source components
4. **Vulnerability Research** - Analyze binary differences before and after CVE patches, reconstruct vulnerability causes and write PoCs
5. **Software Supply Chain Verification** - Reverse engineer third-party closed-source dependencies, check for backdoors or unsafe behavior

---

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **radare2** | Full-featured reverse engineering framework, static/dynamic analysis, script automation | `r2 -A binary && afl \|\| pdf @ main` |
| **ghidra** | NSA open-source reverse engineering platform, decompiler, GUI, headless batch analysis | `analyzeHeadless /tmp project binary` |
| **objdump** | Quick disassembly, ELF/PE structure viewing | `objdump -d -M intel binary` |
| **gdb** | Dynamic debugger, breakpoints, registers, memory inspection | `gdb ./binary && break main && run` |
| **checksec** | Binary security mechanism detection (NX, ASLR, Canary, PIE, RELRO) | `checksec --file=binary` |
| **ROPgadget** | ROP gadget search and chain construction | `ROPgadget --binary binary --ropchain` |
| **binwalk** | Firmware signature identification and extraction | `binwalk -Me firmware.bin` |
| **readelf** | In-depth ELF format analysis (section table, symbol table, relocation) | `readelf -a binary` |
| **strings** | Quick extraction of readable strings for information gathering | `strings -n 8 binary` |

---

## Methodology

### Attack Chain

```
Binary ID           Static Analysis       Dynamic Analysis     Vulnerability Discovery
(file, checksec)  (r2 -A, objdump)     (gdb, r2 -d)        (pattern, fuzz)
     |                 |                 |               |
     v                 v                 v               v
Security Assessment  Exploit Dev         Shellcode          Report & Fix
(ASLR, Canary,     (ROP chain,         (arch adaptation,   (root cause analysis,
 NX, PIE, RELRO)   ret2libc)           encoding bypass)    hardening advice)
```

**Phase Details**:

1. **Binary Identification** - Use `file` to determine architecture and format, `checksec` to assess protection mechanism strength
2. **Static Analysis** - radare2 deep analysis (`aaa`), identify function lists, strings, cross-references, control flow
3. **Dynamic Analysis** - Set breakpoints in GDB/radare2 debug mode, track register and memory state changes
4. **Vulnerability Discovery** - Locate dangerous function calls (`strcpy`/`sprintf`/`printf`), calculate overflow offsets
5. **Exploit Development** - Choose exploitation strategy based on checksec results (ROP, ret2libc, ret2plt)
6. **Shellcode** - Write or adapt shellcode for the target architecture, handle bad characters and encoding

## Practical Steps

> **For detailed commands and payloads see `payloads.md`, and for the complete test checklist see `test-cases.md`.** Below is a summary of core operations for each phase.

### 1. radare2 Analysis Workflow

```bash
# Quick analysis mode (recommended for daily use)
r2 -A binary              # Load and auto-analyze (equivalent to aaa)

# Deep analysis mode (complex targets)
r2 -AA binary             # Deeper auto-analysis

# Common analysis commands
afl                       # List all functions
iz                        # Extract all strings (including data segments)
pdf @ sym.main            # Disassemble main function
axt sym.imp.strcpy        # Find all cross-references to strcpy
iS                        # Section table info (.text, .data, .bss)
ii                        # Import function table
VV                        # Visual control flow graph mode

# Debug mode
r2 -d binary              # Load in debugger mode
db main                   # Set breakpoint at main
dc                        # Continue execution
dr                        # Display register state
px @ rsp                  # Inspect stack memory
```

# Step 1: checksec confirms protection status
checksec --file=binary
#    NX      : disabled    --> Shellcode executable on stack
#    Canary  : disabled    --> No stack protection
#    PIE     : disabled    --> Fixed addresses

# Step 2: radare2 locate dangerous functions
r2 -A binary
afl | grep -E "strcpy|sprintf|gets|read"
pdf @ sym.vulnerable_function
# Observe buffer size and dangerous function calls

# Step 3: Use pattern to calculate offset
# Generate unique pattern (in GDB)
gdb ./binary
pattern_create 200
run $(pattern)
# Observe crash value overwriting RIP/EIP
pattern_offset <crash_value>
```

### 3. ROP Chain Construction

```bash
# Search available gadgets
ROPgadget --binary binary --only "pop|ret"
ROPgadget --binary binary --only "int|ret"

# Auto-generate ROP chain
ROPgadget --binary binary --ropchain

# Search gadgets in radare2
r2 -A binary
/R pop rdi; ret           # Search specific gadget sequence
/R ret                    # Search ret gadget (for stack alignment)

# Common exploitation strategy selection:
# - NX disabled  --> Direct shellcode on stack
# - NX enabled, no ASLR --> ret2shellcode (BSS section)
# - NX + ASLR    --> ret2libc / ROP / ret2plt
```

### 4. radare2 Script Automation

```python
#!/usr/bin/env python3
"""r2pipe automation script - batch vulnerability scanning"""
import r2pipe

def analyze_binary(filepath):
    r2 = r2pipe.open(filepath)
    r2.cmd("aaa")  # Deep analysis

    # Extract key information
    functions = r2.cmd("afl")
    strings = r2.cmd("iz")

    # Scan for dangerous function calls
    dangerous = ["strcpy", "sprintf", "gets", "strcat", "printf"]
    findings = []
    for func in dangerous:
        xrefs = r2.cmd(f"axt sym.imp.{func}")
        if xrefs.strip():
            findings.append({"function": func, "xrefs": xrefs})

    # Check for hidden functions (uncalled symbols)
    all_funcs = r2.cmd("afl~sym.").strip().split("\n")
    # Cross-reference analysis to find orphaned functions

    r2.quit()
    return {"file": filepath, "findings": findings, "functions": functions}
```

### 5. checksec Security Assessment and Exploitation Strategy

```bash
# Complete security assessment
checksec --file=binary --output=json

# Strategy selection based on protection combination:
# +---------+--------+--------+------------------+
# | NX      | ASLR   | Canary | Strategy          |
# +---------+--------+--------+------------------+
# | off     | off    | off    | Direct shellcode   |
# | on      | off    | off    | ret2libc           |
# | on      | on     | off    | ROP + info leak    |
# | on      | on     | on     | Leak + ROP         |
# +---------+--------+--------+------------------+

# Verify ASLR status
cat /proc/sys/kernel/randomize_va_space
# 0 = disabled, 1 = partial randomization, 2 = full randomization

# Compile unprotected binary (for practice)
gcc -o target target.c -fno-stack-protector -z execstack -no-pie
```

---

## Defense Evasion Techniques

### Anti-Debugging
- **ptrace self-attach**: Process attaches to itself via `ptrace(PTRACE_TRACEME, 0, 0, 0)`; prevents gdb from attaching.
- **Timing checks**: Measure time between two `rdtsc` instructions; debugger introduces delay.
- **INT 3 detection**: Scan own code for `0xCC` byte (breakpoint instruction); alert if found.
- **Hardware breakpoint detection**: Check debug registers (`DR0-DR7`) via `/proc/self/status` or `get_thread_area()`.
- **Single-step detection**: Set Trap Flag (`EFLAGS.TF`); check if SIGTRAP handler receives unexpected signal.
- **Debug register poisoning**: Set DR0 to invalid address; cause debugger to crash when continuing.

### Anti-VM / Anti-Sandbox
- **MAC address check**: VMware uses `00:50:56`, `00:0C:29`; VirtualBox uses `08:00:27`; Hyper-V uses `00:15:5D`.
- **CPU vendor check**: `cpuid` instruction reveals hypervisor bit (CPUID.1:ECX[31]).
- **Timing anomalies**: RDTSC inside VM shows non-monotonic or jittered timestamps.
- **Registry artifacts** (Windows): `HKLM\SOFTWARE\VMware, Inc.\VMware Tools`; `HKLM\HARDWARE\DESCRIPTION\System\BIOS` (SystemManufacturer).
- **Filesystem artifacts**: `/proc/vz` (OpenVZ); `/proc/xen` (Xen); `/sys/class/dmi/id/product_name` (VMware/VirtualBox/Hyper-V).
- **Process list check**: `vmtoolsd.exe` (VMware); `vboxservice.exe` (VirtualBox); `prl_tools_service.exe` (Parallels).

### Code Obfuscation
- **Packing**: UPX, ASPack, Themida, VMProtect; detect via high-entropy sections and few imports.
- **Polymorphic code**: Each execution generates different decryption key; same payload, different bytes.
- **Metamorphic code**: Virus body is rewritten each generation (no static signature).
- **Control flow flattening**: Replace `if-else` chains with switch dispatcher; defeats static analysis.
- **Junk code insertion**: Insert no-op instructions (`xchg eax, eax`) between real instructions.
- **Opaque predicates**: Conditions that always evaluate the same but are hard to statically determine.
- **String encryption**: Encrypt sensitive strings; decrypt only at use; revealed via dynamic analysis only.

### Anti-Instrumentation
- **Frida detection**: Scan for `frida-agent` in `/proc/self/maps`; check for `gum-js-loop` thread; detect `frida-server` port (27042).
- **Hook detection**: Compare function prologue in memory vs on-disk; detect inline hooks.
- **Inline syscall invocation**: Use raw syscalls via `syscall` (x64) or `int 0x80` (x86) to bypass libc hooks.
- **Self-integrity check**: Compute hash of own `.text` section; abort if modified (defeats inline hooks).

### Anti-Analysis Files
- **Anti-disassembly**: Insert `jmp` to next instruction +垃圾 byte; confuses linear sweep disassemblers.
- **Anti-IDA patterns**: Use instructions IDA handles poorly (e.g., `aaa` register on x86_64, `BSWAP` with 16-bit operand).
- **Resource section abuse**: Embed misleading PE resources (icon, version info) to confuse analysts.
- **PDB path spoofing**: Compile with fake PDB path (`cargo build` with custom debug info).

### Stealth Execution
- **Process hollowing**: Replace legitimate process memory with malicious code; appears as `explorer.exe` etc.
- **Process injection**: Inject DLL / shellcode into running process via `CreateRemoteThread` or `QueueUserAPC`.
- **Reflective DLL injection**: Load DLL from memory without touching disk; no file artifacts.
- **Atom bombing**: Use Global Atom Table to deliver payload to other processes.
- **Process doppelgänging**: Use Transactional NTFS to load process from rolled-back file.

### Network C2 Stealth
- **Domain fronting**: Use CDN for C2; appears as legitimate CDN traffic.
- **TLS fingerprinting**: Use `curl-impersonate` or custom TLS stack to match Chrome / Firefox JA3 hash.
- **Protocol camouflage**: C2 over DNS, ICMP, HTTPS (mimicking legitimate API calls).
- ** beaconing jitter**: Random intervals between C2 check-ins to evade statistical detection.

---
