# reverse-engineering-advanced — payloads (verbatim from kali-claw)

# Reverse Engineering Advanced — Payloads & Commands

> Operational commands for advanced reverse engineering: symbolic execution, binary diffing, firmware RE, OLLVM deobfuscation, and decompiler workflows. Each section focuses on a specific RE technique. Use during triage, static analysis, dynamic analysis, and reporting.

## Section 1 — Static triage

### 1.1 File identification

```bash
file binary
sha256sum binary
strings binary | head -20

# Section analysis
python3 << 'EOF'
import pefile
pe = pefile.PE('binary.exe')
print(f"Machine: {hex(pe.FILE_HEADER.Machine)}")
print(f"Sections: {len(pe.sections)}")
for s in pe.sections:
    name = s.Name.decode().rstrip(chr(0))
    print(f"  {name:12s} VA={hex(s.VirtualAddress)} entropy={s.get_entropy():.2f}")
EOF
```

### 1.2 ELF analysis

```bash
# ELF
readelf -h binary
readelf -S binary  # Sections
readelf -d binary  # Dynamic
readelf -l binary  # Program headers

# Symbol table
nm binary 2>/dev/null | head -20
nm -D binary 2>/dev/null | head -20  # Dynamic symbols

# Imported functions
objdump -T binary | head
objdump -R binary | head  # Relocations
```

### 1.3 Strings + categorization

```bash
strings -a binary > strings.txt
strings -el binary > strings_wide.txt  # UTF-16

# Find interesting strings
grep -iE "http[s]?://" strings.txt
grep -iE "[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" strings.txt
grep -iE "password|secret|key" strings.txt
```

## Section 2 — Symbolic execution with angr

### 2.1 Basic angr solve

```python
import angr

proj = angr.Project('./crackme', auto_load_libs=False)
state = proj.factory.entry_state()

# Explore - find success, avoid failure
sm = proj.factory.simulation_manager(state)
sm.explore(
    find=lambda s: b'Good boy' in s.posix.dumps(1),
    avoid=lambda s: b'Bad boy' in s.posix.dumps(1)
)

if sm.found:
    found = sm.found[0]
    print(f"Solution: {found.posix.dumps(0)}")
else:
    print("No solution found")
```

### 2.2 angr with hooks

```python
import angr

proj = angr.Project('./binary', auto_load_libs=False)

# Hook complex function with simpler one
class CustomCheck(angr.SimProcedure):
    def run(self, arg):
        return self.state.solver.If(arg > 100, 1, 0)

proj.hook_symbol('complex_check', CustomCheck())

state = proj.factory.entry_state()
sm = proj.factory.simulation_manager(state)
sm.explore(find=0x400a00, avoid=0x400a50)
```

### 2.3 angr memory exploration

```python
import angr

proj = angr.Project('./binary', auto_load_libs=False)
state = proj.factory.entry_state()

# Set symbolic stdin
stdin_size = 32
stdin = angr.BVS('stdin', stdin_size * 8)
state.regs.rdi = stdin

# Find / avoid
sm = proj.factory.simulation_manager(state)
sm.explore(find=0x400a00, avoid=0x400a50)

if sm.found:
    found = sm.found[0]
    print(f"Solution: {found.solver.eval(stdin, cast_to=bytes)}")
```

### 2.4 angr with constraints

```python
import angr

proj = angr.Project('./binary', auto_load_libs=False)
state = proj.factory.entry_state()

# Add constraints on input (e.g., printable ASCII)
for i in range(32):
    byte = state.posix.stdin.load(i, 1)
    state.solver.add(byte >= 0x20)
    state.solver.add(byte <= 0x7e)

sm = proj.factory.simulation_manager(state)
sm.explore(find=0x400a00)

if sm.found:
    print(sm.found[0].posix.dumps(0))
```

## Section 3 — KLEE (LLVM symbolic execution)

### 3.1 Compile to LLVM bitcode

```bash
# Compile C to LLVM bitcode
clang -emit-llvm -c -g program.c -o program.bc

# Run KLEE
klee program.bc

# Solutions in klee-last/
ls klee-last/
# *.ktest files contain solutions

# Read solution
ktest-tool klee-last/test000001.ktest
```

### 3.2 KLEE with assertions

```c
// program.c
#include <klee/klee.h>

int check(int x) {
    if (x * 2 + 1 == 0x12345) {
        return 1;  // success
    }
    return 0;
}

int main() {
    int x;
    klee_make_symbolic(&x, sizeof(x), "x");
    return check(x);
}
```

```bash
clang -emit-llvm -c program.c -o program.bc
klee program.bc
```

## Section 4 — Manticore

### 4.1 Basic manticore

```python
from manticore.ethereum import SolidityContract

# Smart contract analysis
m = ManticoreEVM()
owner = m.create_account(owner=True)
user = m.create_account()

contract = m.solidity_create_contract(
    'Vulnerable.sol',
    owner=owner,
    args=[]
)

# Symbolic argument
symbolic_value = m.make_symbolic_value()
contract.f(symbolic_value)

# Find assertion violation
for state in m.running_states:
    if state.can_complete:
        print("Solution found")
```

### 4.2 Manticore for binary

```python
from manticore.native import Manticore

m = Manticore('./binary', stdin_payload=b'A' * 32)

@m.hook(0x400a00)
def success(state):
    print(f"Solution: {state.solve()}")
    m.terminate()

@m.hook(0x400a50)
def fail(state):
    m.terminate()

m.run()
```

## Section 5 — Binary diffing

### 5.1 BinDiff

```bash
# Install BinDiff (Google/Zynamics)
# https://www.zynamics.com/bindiff.html

# Run from CLI
bindiff --binary1=original.exe --binary2=patched.exe --output_dir=diffs/

# Open in BinDiff GUI
# View function changes
# Filter by similarity score
```

### 5.2 Diaphora (IDA plugin)

```bash
# Install Diaphora (free)
# https://github.com/joxeankoret/diaphora

# In IDA:
# 1. Open original.exe
# 2. File → Script File → diaphora.py
# 3. Export to database
# 4. Open patched.exe
# 5. Diff with previous database
# 6. View best matches / partial matches
```

### 5.3 Patch diff (CVE analysis)

```bash
# 1. Get pre-patch binary (from software vendor archive)
# 2. Get post-patch binary (latest version)
# 3. BinDiff / Diaphora
# 4. Identify changed functions (similarity < 1.0)
# 5. Analyze changed function → identify CVE

# Example: CVE-2021-34527 (PrintNightmare)
# Compare pre-patch C:\Windows\System32\spoolsv.exe
# With post-patch version
```

## Section 6 — Firmware analysis

### 6.1 Binwalk scan

```bash
binwalk firmware.bin

# Output:
# DECIMAL       HEX         DESCRIPTION
# --------------------------------------------------------------------------------
# 0             0x0         TP-Link firmware header...
# 14592         0x3900      LZMA compressed data...
# 1038416       0xFD6F0     SquashFS filesystem...

# Extract
binwalk -e firmware.bin

# View extracted
ls _firmware.bin.extracted/
# squashfs-root/
```

### 6.2 Filesystem analysis

```bash
cd _firmware.bin.extracted/squashfs-root/

# Web server files
ls -la usr/www/
find . -name "*.cgi"
find . -name "*.php"

# Config files
find . -name "*.conf" -o -name "*.cfg"
cat etc/passwd  # Default credentials?
cat etc/shadow  # Password hashes

# Telnet / SSH config
cat etc/inetd.conf 2>/dev/null
cat etc/init.d/S50sshd 2>/dev/null
```

### 6.3 FACT (Firmware Analysis Compare Tool)

```bash
git clone https://github.com/fkie-cad/FACT_core
cd FACT_core
./install

# Start FACT
./start_all_installed_fact_components

# Web UI: https://localhost:5000
# Upload firmware → automated analysis
```

### 6.4 EMBA (firmware analyzer)

```bash
git clone https://github.com/e-m-b-a/emba
cd emba
./installer.sh

# Run on firmware
sudo ./emba -l /logs -f firmware.bin

# Output: HTML report + CVE matches
```

### 6.5 Hardcoded credentials

```bash
# Search for hardcoded credentials
cd _firmware.bin.extracted/squashfs-root/
grep -rE "password|passwd|admin|root" --include="*.conf" --include="*.cfg" --include="*.sh" | head -30

# Telnet default creds
cat etc/init.d/rcS 2>/dev/null | grep -iE "telnetd|passwd"

# SSH default keys
ls -la etc/dropbear/ 2>/dev/null
cat etc/dropbear/dropbear_rsa_host_key 2>/dev/null | head
```

## Section 7 — OLLVM deobfuscation

### 7.1 Identify OLLVM CFF (Control Flow Flattening)

```python
# Visual signature: large dispatcher function with switch statement
# In Ghidra / IDA:
# 1. Open binary
# 2. View CFG (Control Flow Graph)
# 3. Look for dispatcher pattern:
#    - Single entry function
#    - Big switch statement on state variable
#    - All basic blocks branch back to dispatcher

# Ghidra script for CFF detection
# @category: Deobfuscation
from ghidra.app.decompiler import DecompInterface

decompiler = DecompInterface()
decompiler.openProgram(currentProgram)

for func in currentProgram.getFunctionManager().getFunctions(True):
    result = decompiler.decompileFunction(func, 60, None)
    if result.decompileCompleted():
        hcode = result.getDecompiledFunction().getC()
        if "switch" in hcode and hcode.count("case") > 10:
            print(f"Possible CFF: {func.getName()} at {func.getEntryPoint()}")
```

### 7.2 Deflattening (deflat.py)

```bash
# https://github.com/cd70s062f/deflat

# Identify dispatcher address
# In IDA: look for big switch

# Run deflat
python3 deflat.py --binary flattened.exe \
  --dispatcher 0x401000 \
  --state-var eax \
  --output deflattened.exe
```

### 7.3 Bogus Control Flow (BCF) removal

```bash
# BCF adds always-true/always-false branches
# Identify opaque predicates

# Pattern: if (x*x % 2 == 0) - always true (squares are even-divisible by 2 if x is even)
# Pattern: if (x^2 + 1 > 0) - always true (squares are non-negative)

# Use semantic-aware tools: miasm, Triton
python3 << 'EOF'
from miasm.analysis.binary import Container
from miasm.analysis.machine import Machine

# Parse binary
cont = Container.from_stream(open('binary', 'rb'))
machine = Machine(cont.arch)
# ...
# Identify opaque predicates via symbolic execution
EOF
```

### 7.4 Instruction Substitution (SUB) reversal

```bash
# SUB replaces simple operations with complex equivalents
# E.g., x + y → (x ^ y) + 2*(x & y)

# Use Triton for simplification
python3 << 'EOF'
from triton import TritonContext, ARCH, Instruction, OPCODE

ctx = TritonContext(ARCH.X86_64)

# Set up symbolic
# Execute + simplify
EOF
```

## Section 8 — Decompiler confusion

### 8.1 Anti-decompiler patterns

```python
# Common anti-decompiler patterns:

# 1. Stack manipulation tricks
# push X; pop Y → mov Y, X (but decompiler may not simplify)

# 2. Self-modifying code
# Code that rewrites itself at runtime

# 3. Overlapping instructions
# Jump into middle of instruction

# 4. Anti-disassembly (JE+0 / JNE-1)
# Two consecutive jumps - one taken, one not
# Forces disassembler down wrong path

# 5. Indirect calls
# call dword ptr [eax+0x4]
# Hard for decompiler to resolve

# 6. Function pointer tables
# Many possible call targets

# 7. Exception-based control flow
# Setjmp / longjmp patterns

# Identify in IDA Python:
import idautils, idc

for func_ea in idautils.Functions():
    for head in idautils.FuncItems(func_ea):
        mnem = idc.print_insn_mnem(head)
        # Look for patterns
        if mnem == "jmp":
            # Check if indirect
            if idc.get_operand_type(head, 0) == idc.o_reg:
                print(f"Indirect jmp at {hex(head)}")
```

### 8.2 Manual deobfuscation

```python
# IDA Python: patch overlapping instructions
import idc

# Original: jmp into middle of instruction
# Patch: NOP out overlapping, replace with direct jmp
idc.patch_byte(0x401000, 0x90)  # NOP
idc.patch_byte(0x401001, 0x90)  # NOP
idc.patch_byte(0x401002, 0xEB)  # jmp short
idc.patch_byte(0x401003, 0x10)  # offset
```

## Section 9 — SMT-assisted analysis (Z3)

### 9.1 Z3 key recovery

```python
from z3 import *

# Input: 16-byte key
key = [BitVec(f'key_{i}', 8) for i in range(16)]

s = Solver()

# Constraints (derived from disassembly)
s.add(key[0] == 0x41)  # 'A'
s.add(key[1] + key[2] == 0xc2)
s.add(key[3] * key[4] == 0x410)
s.add(key[5] - key[6] == 5)
s.add(key[7] ^ key[8] == 0x10)

# All printable
for i in range(16):
    s.add(key[i] >= 0x20)
    s.add(key[i] <= 0x7e)

if s.check() == sat:
    m = s.model()
    print(bytes(m[k].as_long() for k in key))
```

### 9.2 Z3 for crypto key

```python
from z3 import *

# Recover XOR key from known plaintext
plaintext = b"Hello World"
ciphertext = b"\x12\x04\x0d\x09\x08\x49\x2a\x1c\x0e\x09\x2f"

# XOR key
key_len = 4
key = [BitVec(f'key_{i}', 8) for i in range(key_len)]

s = Solver()

for i in range(len(plaintext)):
    s.add((plaintext[i] ^ key[i % key_len]) == ciphertext[i])

if s.check() == sat:
    m = s.model()
    print(bytes(m[k].as_long() for k in key))
```

## Section 10 — Variant analysis

### 10.1 Kam1n0 clustering

```bash
# Install Kam1n0 (https://github.com/McGill-DMaS/Kam1n0-Community)

# Index samples
kam1n0 index -i samples/

# Cluster
kam1n0 cluster -i samples/ -o clusters.json

# View clusters
jq '.clusters[] | .name' clusters.json
```

### 10.2 BinDiff multi-binary

```bash
# Diff all pairs in directory
for f1 in samples/*; do
    for f2 in samples/*; do
        [ "$f1" = "$f2" ] && continue
        bindiff --binary1=$f1 --binary2=$f2 --output_dir=diffs/$(basename $f1)_$(basename $f2)/
    done
done
```

### 10.3 Diaphora multi-diff

```bash
# In IDA:
# 1. For each sample: Export to SQLite database
# 2. Diff each pair
# 3. Track similarity scores

# Script to bulk export
for f in samples/*; do
    ida -A -S"diaphora.py --export-only" $f
done
```

## Section 11 — Ghidra workflows

### 11.1 Ghidra headless analysis

```bash
analyzeHeadless /tmp proj -import binary -postScript MyScript.py -scriptPath /path/to/scripts

# Example script
cat > MyScript.py << 'EOF'
from ghidra.program.model.symbol import SymbolType

sm = currentProgram.getSymbolTable()
for sym in sm.getAllSymbols(True):
    if sym.getSymbolType() == SymbolType.FUNCTION:
        print(f"{sym.getName()} at {sym.getAddress()}")
EOF
```

### 11.2 Ghidra Python decompile

```python
# In Ghidra Script Manager
from ghidra.app.decompiler import DecompInterface

decompiler = DecompInterface()
decompiler.openProgram(currentProgram)

for func in currentProgram.getFunctionManager().getFunctions(True):
    result = decompiler.decompileFunction(func, 60, None)
    if result.decompileCompleted():
        hcode = result.getDecompiledFunction().getC()
        print(f"// Function: {func.getName()}")
        print(hcode)
```

### 11.3 Ghidra script: find crypto constants

```python
# Search for known crypto constants
crypto_constants = {
    "AES_SBOX": bytes([0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5]),
    "MD5_INIT": 0x67452301,
    "SHA256_INIT": 0x6a09e667,
    "AES_RCON": 0x9d,
}

mem = currentProgram.getMemory()
for name, const in crypto_constants.items():
    if isinstance(const, int):
        addr = findBytes(toAddr(0), struct.pack('>I', const), None, True, None)
    else:
        addr = findBytes(toAddr(0), const, None, True, None)
    if addr:
        print(f"Found {name} at {addr}")
```

## Section 12 — IDA Pro workflows

### 12.1 IDA Python batch analysis

```python
import idautils, idc, ida_hexrays

# Initialize Hex-Rays
ida_hexrays.init_hexrays_plugin()

# Iterate all functions
for func_ea in idautils.Functions():
    name = idc.get_func_name(func_ea)
    size = idc.get_func_attr(func_ea, idc.FUNCATTR_END) - func_ea

    if size > 1000:  # Large function
        print(f"Large function: {name} ({size} bytes)")

        # Decompile
        cf = ida_hexrays.decompile(func_ea)
        if cf:
            print(cf)
```

### 12.2 IDA batch script

```bash
# Run script on all binaries
for f in samples/*; do
    ida -A -S"analysis.py" $f
done
```

### 12.3 IDA Python: find injections

```python
import idautils, idc

# Find VirtualAlloc + WriteProcessMemory patterns
suspicious_apis = ["VirtualAlloc", "VirtualProtect", "WriteProcessMemory",
                   "CreateRemoteThread", "NtUnmapViewOfSection"]

imports = []
for ea in idautils.Functions():
    name = idc.get_func_name(ea)
    if name in suspicious_apis:
        imports.append((name, ea))

for name, ea in imports:
    callers = list(idautils.XrefsTo(ea))
    if callers:
        print(f"{name} called by {len(callers)} functions")
        for xref in callers[:5]:
            print(f"  Caller: {hex(xref.frm)}")
```

## Section 13 — Binary Ninja workflows

### 13.1 Binary Ninja Python

```python
import binaryninja as bn

bv = bn.load("binary.exe")

# Iterate functions
for func in bv.functions:
    print(f"{func.name}: {hex(func.start)}")
    # Iterate basic blocks
    for bb in func.basic_blocks:
        print(f"  BB at {hex(bb.start)}")
```

### 13.2 Binary Ninja API

```python
import binaryninja as bn

bv = bn.load("binary.exe")

# Find calls to VirtualAlloc
for func in bv.functions:
    for callee in func.callees:
        if "VirtualAlloc" in callee.name:
            print(f"{func.name} calls VirtualAlloc at {hex(func.start)}")
```

## Section 14 — radare2 workflows

### 14.1 r2 batch analysis

```bash
r2 -A -q -c "afl" binary

# Multi-binary
for f in samples/*; do
    r2 -A -q -c "afl; ii" $f > analysis_$(basename $f).txt
done
```

### 14.2 r2 decompile

```bash
r2 -A binary

# In r2 prompt:
pdf @ main  # disassemble main
pdc @ main  # pseudo-C decompile
```

## Section 15 — Crypto identification

### 15.1 Find AES

```bash
# AES S-box starts: 63 7c 77 7b f2 6b 6f c5
# Look in binary
xxd binary | grep -E "63.*7c.*77.*7b.*f2.*6b.*6f.*c5"

# Or in Python:
python3 << 'EOF'
with open('binary', 'rb') as f:
    data = f.read()

aes_sbox = bytes([0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5])
offset = data.find(aes_sbox)
if offset >= 0:
    print(f"AES S-box at offset {hex(offset)}")
EOF
```

### 15.2 Find RSA

```bash
# RSA public key typically stored as ASN.1 DER
# Header: 30 82 XX XX 02 82 XX XX 00

xxd binary | grep -E "^.*: 30 82.*02 82.*00"

# Or in Python:
python3 << 'EOF'
with open('binary', 'rb') as f:
    data = f.read()

# RSA DER pattern
import re
matches = re.findall(b'\x30\x82.{2}\x02\x82.{2}\x00', data, re.DOTALL)
print(f"Possible RSA public keys: {len(matches)}")
EOF
```

### 15.3 Find DES

```bash
# DES S-boxes are well-known
# S1 starts: 0x0e, 0x04, 0x0d, 0x01

xxd binary | grep -E "0e 04 0d 01"
```

## Section 16 — Equation Group / Pegasus-style obfuscation

### 16.1 Multi-layer obfuscation

```python
# Equation Group binaries use:
# - Custom packers
# - Encrypted sections
# - Self-modifying code
# - Virtualized code (VMProtect-style)

# Multi-layer unpacking workflow:
# 1. Static analysis (identify outer packer)
# 2. Dynamic analysis (let packer unpack to layer 2)
# 3. Memory dump (capture layer 2)
# 4. Repeat until original code found

# Use pe-sieve for memory dumps
pe-sieve /pid 1234 /imp 3 /dump
```

### 16.2 Pegasus-specific (Citizen Lab workflow)

```bash
# Pegasus uses:
# - SMS / iMessage exploitation
# - Memory-only operation (no files)
# - Encrypted C2
# - Self-destruct mechanism

# Analysis (Citizen Lab):
# 1. MobileVerificationToolkit (MVT)
pip install mvt

mvt-ios check-backup --output ./output/ ./backup/

# 2. Look for indicators of compromise
# - Suspicious SMS / iMessage
# - Network anomalies
# - Filesystem artifacts
```

## Section 17 — Custom unpacking

### 17.1 Manual unpacking workflow

```bash
# 1. Identify OEP (Original Entry Point)
#    - Look for transitions from packer code to original code
#    - Common: jmp / call to non-packed section

# 2. Set breakpoint at suspected OEP
#    - In x64dbg: bp <address>

# 3. Run until OEP reached
#    - Use memory breakpoint on packed section to catch unpacker transition

# 4. Dump process memory
#    - Scylla plugin
#    - pe-sieve /pid $PID /imp 3 /dump

# 5. Fix IAT (Import Address Table)
#    - Scylla: IAT AutoSearch → Get Imports → Fix Dump
```

### 17.2 Memory dump with pe-sieve

```bash
# After reaching OEP in debugger
pe-sieve /pid 1234 /imp 3 /dump

# Output: process_1234_*.exe files
ls -la process_1234_*
```

## Section 18 — Reporting

### 18.1 RE report template

```markdown
# Reverse Engineering Report

## Executive Summary
- Binary: sample.exe
- SHA256: abc...
- Type: PE32 executable
- Purpose: Credential stealer

## Static Analysis
### Architecture
- x86-64 (64-bit Windows)

### Sections
| Name | Entropy | Packed |
|------|---------|--------|
| .text | 6.45 | No |
| .data | 7.12 | No |
| .vmp0 | 7.95 | Yes |

### Imports
- ADVAPI32: RegOpenKeyA, RegSetValueA
- KERNEL32: CreateFileA, WriteFile
- WININET: InternetOpenA, HttpSendRequestA

## Dynamic Analysis
- Process injection: Yes (svchost.exe)

<!-- truncated for token budget; see external/kali-claw for the rest -->

