# digital-forensics

# Skill: Digital Forensics

> **Supplementary Files**:
> - `payloads.md` — Forensics command reference covering disk imaging, filesystem analysis, memory forensics, network forensics, log analysis, timeline reconstruction, file carving, anti-forensics detection, Windows/Linux forensics, and more
> - `test-cases.md` — Structured test case list covering evidence acquisition, filesystem analysis, memory forensics, network forensics, and anti-forensics detection

## Summary

Digital Forensics skill domain covering forensics operations.

**Tools**: autopsy, sleuth kit, volatility, wireshark/tshark, binwalk, foremost, Autopsy, SleuthKit (+2 more)

**Domain**: forensics

## Description

Digital forensics covers the complete workflow of disk forensics, memory forensics, network forensics, file recovery/carving, and chain of custody. The core objective is to extract, analyze, and present admissible electronic evidence from digital media while maintaining evidence integrity and legal validity.

The agent has mastered the SleuthKit command-line toolset (mmls, fsstat, fls, icat, ifind, ils), Autopsy forensics platform, Scalpel/Foremost file carving, Bulk Extractor high-performance extraction, ExifTool metadata analysis, PhotoRec data recovery, TestDisk partition repair, and has Volatility memory analysis and Wireshark/tshark network forensics capabilities.

## Use Cases

1. **Incident Response Forensics** - After a security incident, perform disk image analysis and memory dump extraction on compromised systems to reconstruct the attack timeline and lateral movement paths
2. **File Recovery and Carving** - Recover deleted files from damaged or formatted disks, reconstruct fragmented data using file header/tail signatures
3. **Malware Forensics** - Extract malicious processes, injected code, and rootkit-hidden modules from memory dumps, combined with disk analysis to locate persistence mechanisms
4. **Network Attack Reconstruction** - Reconstruct network attack traffic through PCAP analysis, identify C2 communications, data exfiltration, and lateral movement behavior
5. **Legal Electronic Evidence** - Strictly follow chain of custody procedures, generate court-admissible forensics reports and hash verification records

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **autopsy** | Web-based forensics platform built on SleuthKit | `autopsy -p 8080 -d /case/evidence` |
| **sleuth kit** | Command-line filesystem forensics toolset | `mmls image.dd && fls -r -o 2048 image.dd` |
| **volatility** | Memory dump analysis framework | `vol.py -f memory.dmp --profile=Win10 pslist` |
| **wireshark/tshark** | Network traffic analysis and PCAP forensics | `tshark -r capture.pcap -Y "http.request" -T fields -e http.host` |
| **binwalk** | Firmware/binary signature identification and extraction | `binwalk -Me firmware.bin` |
| **foremost** | Signature-based data carving | `foremost -t jpg,png,pdf -i image.dd -o /recovery` |

## Methodology

### Attack Chain

```
Evidence Collection    Disk Analysis        Memory Analysis      Network Reconstruction
(Imaging/Hash/         (Partition/          (Process/Injection/  (PCAP/C2/Data
 Write-Blocking)        Filesystem/Deleted)  Rootkit)             Exfiltration)
       |                    |                     |                      |
       v                    v                     v                      v
                Timeline Building        Report & Presentation
                (MAC Times/Event         (Chain of Custody/
                 Correlation)             Admissible Report)
```

**Phase Details**:

1. **Evidence Collection** - Use hardware write-blockers to prevent tampering, create bit-by-bit images of original media (dd / dcfldd / FTK Imager), calculate MD5/SHA256 hash verification values, and complete chain of custody forms
2. **Disk Analysis** - Use mmls for partition table analysis, fsstat for filesystem examination, fls for file/directory listing, and icat for file content extraction, focusing on searching for deleted files, hidden partitions, and slack space
3. **Memory Analysis** - Use Volatility to extract running processes (pslist/pstree), network connections (netscan), DLL injections (malfind), and registry hives (hivelist), identifying malicious code residency and rootkit hiding
4. **Network Reconstruction** - Use tshark to filter and analyze network traffic, reconstruct DNS queries, HTTP requests, TLS handshake metadata, and identify C2 communication patterns and data exfiltration behavior
5. **Timeline Building** - Combine disk MAC times (fls -m), network traffic timestamps, and memory process creation times; use log2timeline/supertimeline to generate a unified event timeline

## Practical Steps

### Step 1: Disk Image Analysis and Autopsy

Create bit-by-bit images and verify hashes, use SleuthKit command-line tools for quick analysis of partition tables, filesystems, and deleted files, or perform interactive forensics analysis through the Autopsy web platform.

### Step 2: Memory Dump Analysis with Volatility

Identify the memory dump's operating system profile, extract process lists and process trees, detect hidden processes, code injection, and API hooks, analyze network connections, and export suspicious processes with their loaded DLLs.

### Step 3: File Carving and Binwalk

Use foremost/scalpel for file signature-based deleted file recovery, use binwalk for recursive extraction of firmware and embedded files, use bulk_extractor for high-performance feature data extraction, and use exiftool for file metadata analysis.

### Step 4: Network Forensics and tshark

Perform traffic statistics and conversation analysis on PCAP files, reconstruct HTTP requests and DNS queries, extract transferred files, analyze TLS handshake metadata to identify C2 communications, and detect data exfiltration techniques such as DNS tunneling.

### Step 5: Timeline Reconstruction

Use SleuthKit to generate MAC timelines, combining disk MAC times, network traffic timestamps, memory process creation times, and system logs to build a unified event timeline that reconstructs the complete attack process.

> **Detailed payloads in `payloads.md`, complete test checklist in `test-cases.md`.**

## Defense Evasion Techniques

### Anti-Forensics
- **Secure deletion**: `shred`, `srm`, `bcwipe` to defeat filesystem recovery.
- **Timestamp manipulation**: NTFS `$STANDARD_INFORMATION` + `$FILE_NAME` (defeat timeline analysis).
- **USN Journal cleaning**: `fsutil usn deletejournal` to remove update sequence records.
- **Log tampering**: Selective log entry removal; preserve legitimate-looking sequence.

### Memory Anti-Forensics
- **Process hollowing**: Replace legitimate process memory; appears legitimate in `ps`.
- **DKOM (Direct Kernel Object Manipulation)**: Unlink process from active list; invisible to live response.
- **Reflective DLL injection**: Load from memory; no file on disk.
- **Memory-only execution**: `memfd_create` on Linux; no disk artifacts.

### Network Anti-Forensics
- **TLS to attacker C2**: Encrypt all traffic; PCAP shows only encrypted bytes.
- **Domain fronting**: Use legitimate CDN; PCAP shows only CDN IP.
- **DNS tunneling**: Encode data in DNS; bypasses HTTP-based PCAP analysis.
- **Covert timing channels**: Encode data in inter-packet delays.

## Advanced Techniques

Advanced forensic analysis includes: Windows registry forensics (ShellBags, UserAssist, ShimCache, Amcache) for detailed user activity reconstruction, hibernation file analysis for recovering memory contents from powered-off systems, Volume Shadow Copy analysis for accessing previous file versions that attackers believed were deleted, and mobile device forensics using Cellebrite or open-source alternatives. For network forensics, advanced techniques include TLS session decryption with captured keys, HTTP/2 and QUIC protocol analysis, and DNS tunnel reconstruction from fragmented query patterns.
