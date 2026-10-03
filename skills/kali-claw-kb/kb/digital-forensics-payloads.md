# digital-forensics — payloads (verbatim from kali-claw)

# Payloads: digital forensics / Digital Forensics

> thisfileas `SKILL.md` Supplementary Files，containsdigital forensicsallprocess commandquick referencemanual。

---

## 1. diskimageandobtain / Disk Imaging and Acquisition

### dd / dcfldd 逐bitimage

```bash
# use dcfldd create逐bitimageandchecksumhash
dcfldd if=/dev/sdb of=evidence.dd hash=sha256 hashlog=hash.txt

# usestandard dd createimage
dd if=/dev/sdb of=evidence.dd bs=4K conv=noerror,sync status=progress

# calculateimagehashchecksumValue
sha256sum evidence.dd > evidence.sha256
md5sum evidence.dd > evidence.md5

# verifyimageintegrity（forthanrawmediaandimage）
dcfldd if=/dev/sdb hash=sha256 hashlog=original.txt verifylog=verify.txt
```

### FTK Imager（GUI Tool）

```bash
# commandrowmodecreateimage
ftk imager.exe evidence.dd --verify

# FTK Imager supports: E01/Ex01 format、compression、inner嵌hash
```

---

## 2. filesystemanalysis / File System Analysis

### SleuthKit commandrowToolset

```bash
# viewpartition tableoffset
mmls evidence.dd

# filesysteminformation
fsstat -o 2048 evidence.dd

# recursivelistfileanddirectory
fls -r -o 2048 evidence.dd

# by inode Extractfilecontent
icat -o 2048 evidence.dd 12345

# listalready delete inode
ils -o 2048 evidence.dd

# findspecifyfilenameforshould inode
ifind -o 2048 -n "secret.doc" evidence.dd

# byblockaddressfindmetadatastructure
blkcat -o 2048 evidence.dd 1024
```

### Autopsy platform

```bash
# start Autopsy Web platform
autopsy -p 8080 -d /case/evidence
# browsetoolaccess http://localhost:8080
# create Case -> add Data Source -> selectimagefile -> selectwhen zone
```

**Autopsy criticalanalysissuccesscan**:
- Data Source -> searchalready knowmaliciousfilehash
- Deleted Files -> recovercomplexalready deletecontent
- File Metadata -> view MAC when timestamp
- Keyword Search -> searchsensitivecritical词
- Extract -> Extract EXIF metadataand地reasoncoordinates

---

## 3. memory forensics / Memory Forensics

### Volatility framework

```bash
# Identifyoperationsystem profile
vol.py -f memory.dmp imageinfo

# processanalysis
vol.py -f memory.dmp --profile=Win10x64_19041 pslist       # 进程列表
vol.py -f memory.dmp --profile=Win10x64_19041 pstree       # 进程树
vol.py -f memory.dmp --profile=Win10x64_19041 psxview      # 检测隐藏进程
vol.py -f memory.dmp --profile=Win10x64_19041 psscan       # 进程扫描（Pool tag）

# maliciouscodeDetect
vol.py -f memory.dmp --profile=Win10x64_19041 malfind      # 检测代码注入
vol.py -f memory.dmp --profile=Win10x64_19041 apihooks     # 检测 API hook
vol.py -f memory.dmp --profile=Win10x64_19041 ssdt         # 检查 SSDT hook

# networkconnectExtract
vol.py -f memory.dmp --profile=Win10x64_19041 netscan      # 网络连接扫描
vol.py -f memory.dmp --profile=Win10x64_19041 connscan     # TCP 连接扫描
vol.py -f memory.dmp --profile=Win10x64_19041 sockets      # Socket 扫描

# Extractcan suspiciousprocess DLL andmemory
vol.py -f memory.dmp --profile=Win10x64_19041 dlllist -p 1234     # DLL 列表
vol.py -f memory.dmp --profile=Win10x64_19041 procdump -p 1234 -D /output  # 进程转储
vol.py -f memory.dmp --profile=Win10x64_19041 dlldump -p 1234 -D /output    # DLL 转储

# registertableanalysis
vol.py -f memory.dmp --profile=Win10x64_19041 hivelist            # 注册表 hive 列表
vol.py -f memory.dmp --profile=Win10x64_19041 printkey -o 0xfffff80  # 打印注册表键值

# credentialsExtract
vol.py -f memory.dmp --profile=Win10x64_19041 hashdump    # SAM 哈希
vol.py -f memory.dmp --profile=Win10x64_19041 cachedump   # 缓存凭据
vol.py -f memory.dmp --profile=Win10x64_19041 mimikatz    # Mimikatz 提取
```

---

## 4. network forensics / Network Forensics

### Wireshark / tshark filtertool

```bash
# basic statisticsand概览
tshark -r capture.pcap -q -z io,stat,1           # 流量统计
tshark -r capture.pcap -q -z conv,ip              # IP 对话统计
tshark -r capture.pcap -q -z endpoints,ip         # 端点统计

# HTTP requestalsooriginal
tshark -r capture.pcap -Y "http.request" -T fields \
  -e frame.time -e ip.src -e http.host -e http.request.uri

# DNS queryanalysis（Identifymaliciousdomain name）
tshark -r capture.pcap -Y "dns.qr==0" -T fields \
  -e frame.time -e ip.src -e dns.qry.name | sort | uniq -c | sort -rn

# Extracttransmissionfile
tshark -r capture.pcap --export-objects http,/output/http_files
tshark -r capture.pcap --export-objects smb,/output/smb_files

# TLS metadata extraction（Identify C2 communication）
tshark -r capture.pcap -Y "tls.handshake.type==1" -T fields \
  -e ip.dst -e tls.handshake.extensions_server_name

# dataexfiltrationDetect（DNS tunnelDetect）
tshark -r capture.pcap -Y "dns" -T fields -e dns.qry.name \
  | awk '{print length, $0}' | sort -rn | head -20

# Extractspecific IP alldepartmentflowamount
tshark -r capture.pcap -Y "ip.addr==192.168.1.100" -w filtered.pcap

# HTTP POST requestbodyExtract
tshark -r capture.pcap -Y "http.request.method==POST" -T fields \
  -e frame.time -e ip.src -e ip.dst -e http.request.uri -e http.file_data

# SMTP mailpieceExtract
tshark -r capture.pcap -Y "smtp" -T fields \
  -e frame.time -e smtp.from -e smtp.to -e smtp.data
```

---

## 5. loganalysiscommand / Log Analysis

```bash
# SSH brute forceDetect
grep "Failed password" /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head

# Apache access loganalysis - statistics HTTP statuscode
awk '{print $9}' /var/log/apache2/access.log | sort | uniq -c | sort -rn

# Nginx log - Extractspecificwhen intervalsegment request
awk '$4 ~ /26\/Apr\/2026:1[0-2]:/' /var/log/nginx/access.log

# system log - Extract sudo operation
grep "sudo:" /var/log/auth.log

# dmesg kernelloganalysis
dmesg -T | grep -i "error\|warn\|fail"

# lastlog userloginrecord
lastlog | grep -v "Never"

# last commandviewloginhistory
last -n 50 -a
```

---

## 6. when timelineanalysis / Timeline Analysis

```bash
# SleuthKit generate MAC when timeline
fls -m "/" -o 2048 evidence.dd > timeline_body.txt
mactime -b timeline_body.txt > timeline.csv

# log2timeline (Plaso) generatesuperlevelwhen timeline
log2timeline.py --storage-file case.plaso /case/evidence
psort.py -o dynamic -w timeline.csv case.plaso

# relatedanalysis（comprehensivedisk + network + memory）
# willwithbelowsource when timestampunifiedimportanalysisTool:
# - disk: fls -m output MAC when interval
# - network: tshark Extract frame.time
# - memory: volatility pslist processcreatewhen interval
# - log: /var/log/auth.log, Windows Event Log

# criticaleventsorting（close注abnormalwhen intervalpoint）
# - filecreate/modify（maliciouspayload落地）
# - processstart（vulnerability exploitationexecute）
# - networkconnect（C2 returnconnect、dataexfiltration）
# - userlogin（lateral movement）
```

---

## 7. filecarving / File Carving

### foremost

```bash
# byspecifyfilesignaturerecovercomplex
foremost -t jpg,png,pdf,doc,zip -i evidence.dd -o /recovery

# recovercomplexall already knowtype
foremost -t all -i damaged_disk.img -o /recovery_all
```

### binwalk

```bash
# Scanfilesignature
binwalk evidence.dd

# recursiveExtractall embedfile
binwalk -Me evidence.dd

# Extractspecifictypefile
binwalk --dd='png:image' firmware.bin
```

### scalpel

```bash
# 精细controlfilecarving
scalpel -c /etc/scalpel/scalpel.conf -o /output evidence.dd
```

### bulk_extractor

```bash
# highitycancharacteristicExtract
bulk_extractor -o /output evidence.dd
# output: email.txt, url.txt, credit_card.txt, phone.txt etc.
```

### exiftool（metadataanalysis）

```bash
# recursiveviewmetadata
exiftool -r /recovery/

# JSON formatoutput
exiftool -json /recovery/*.jpg

# close注: GPS coordinates、createwhen interval、deviceinformation、modifyhistory
```

---

## 8. anti-forensicsDetect / Anti-Forensics Detection

```bash
# Detectwhen timestamptamper（Timestomping）
# forthanfilesystem MAC when intervalandfilecontentmetadata notconsistent
fls -m "/" -o 2048 evidence.dd | sort -k 3,3 > mac_times.txt

# Detectdisk擦除trace
# viewdisk末尾andnot partmatch空intervaliswhetherby清零
dd if=evidence.dd bs=1M skip=XXXX count=1 | xxd | head -20

# Detectencryptioncontainer
binwalk evidence.dd | grep -i "truecrypt\|veracrypt\|luks"

# Detect Steganography（隐write）
steghide extract -sf suspicious.jpg -p ""
stegseek --crack suspicious.jpg /usr/share/wordlists/rockyou.txt

# Detectlogclear
# forthanlogfile continuousityandwhen intervalinterval隔abnormal
awk 'NR>1 {print prev, $0, $0-prev} {prev=$0}' /var/log/syslog

# Detect ADS（Alternate Data Streams）- NTFS
# in Windows imageincheck
streams -s suspicious_file.exe
```

---

## 9. Windows forensics / Windows Forensics

### registertableanalysis

```bash
# use Volatility Extractregistertable hive
vol.py -f memory.dmp --profile=Win10x64_19041 hivelist
vol.py -f memory.dmp --profile=Win10x64_19041 printkey -o 0xfffff80 -K "Software\Microsoft\Windows\CurrentVersion\Run"

# common registertableforensicsbitconfiguration
# HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run - fromstartitem
# HKLM\SYSTEM\CurrentControlSet\Services - serviceitem
# HKLM\SAM - useraccountandpasswordhash
# HKLM\SYSTEM\MountedDevices - mountdevicerecord
# NTUSER.DAT\Software\Microsoft\Windows\CurrentVersion\Explorer - useractivity
```

### Windows event log

```bash
# use Volatility Extractevent log
vol.py -f memory.dmp --profile=Win10x64_19041 evtlogs -D /output

# criticalevent ID
# 4624 - successlogin / 4625 - loginfailure
# 4688 - processcreate / 4689 - processterminate
# 4720 - useraccountcreate / 4728/4732 - useraddtoadministratorgroup
# 7045 - serviceinstall / 7036 - servicestatuschange
# 1102 - audit logclear
# 4697 - serviceinstall（maliciousserviceDetect）

# use LogParser analysis .evtx
LogParser.exe -i:EVT "SELECT TimeGenerated, SourceName, EventID, Message FROM security.evtx WHERE EventID=4624"
```

---

## 10. Linux forensics / Linux Forensics

### /var/log system log

```bash
# auth.log - authenticationlog
cat /var/log/auth.log | grep -i "accepted\|failed\|invalid"

# syslog - systemmessage
cat /var/log/syslog | grep -i "error\|fail\|critical"

# kern.log - kernellog
cat /var/log/kern.log

# usercommandhistory
cat ~/.bash_history
cat ~/.zsh_history

# userloginrecord
last -f /var/log/wtmp
lastb -f /var/log/btmp  # 失败登录

# cron log
cat /var/log/cron.log
grep -i "cron" /var/log/syslog
```

### journalctl (systemd)

```bash
# viewalldepartmentlog
journalctl --no-pager

# bywhen intervalscopefilter
journalctl --since "2026-04-25 00:00:00" --until "2026-04-26 00:00:00"

# byservicefilter
journalctl -u sshd
journalctl -u apache2

# byPriorityfilter
journalctl -p err -b    # 当前启动的错误级别日志

# byprocess PID filter
journalctl _PID=1234

# viewstartlog
journalctl -b -1   # 上一次启动
journalctl -b 0    # 当前启动

# outputas JSON（thenatfollow-upanalysis）
journalctl -o json-pretty --since "2026-04-25"
```

### /proc and /etc forensics

```bash
# currentrunprocess
ps auxf
ls -la /proc/[0-9]*/exe    # 进程可执行文件链接
ls -la /proc/[0-9]*/fd     # 进程文件描述符

# already mountfilesystem
cat /proc/mounts
findmnt

# networkconnect
ss -tulpn
cat /proc/net/tcp

# 定when task
crontab -l
cat /etc/crontab
ls -la /etc/cron.*
ls -la /var/spool/cron/

# userandgroup
cat /etc/passwd | grep -v "nologin\|false"
cat /etc/shadow
cat /etc/group
```

---

## 11. Memory Acquisition

### LiME (Linux Memory Extractor)

```bash
# Build LiME kernel module for target system
cd LiME/src
make
# Load module and dump memory to file
insmod lime-$(uname -r).ko "path=/tmp/memory.lime format=lime"

# Dump memory over network (avoid writing to target disk)
insmod lime-$(uname -r).ko "path=tcp:4444 format=lime"
# On forensic workstation:
nc target_ip 4444 > memory.lime

# Dump memory in raw format (compatible with more tools)
insmod lime-$(uname -r).ko "path=/tmp/memory.raw format=raw"

# Dump memory with timeout (for large RAM systems)
insmod lime-$(uname -r).ko "path=/tmp/memory.lime format=lime timeout=0"

# Verify dump integrity
sha256sum /tmp/memory.lime > /tmp/memory.lime.sha256
```

### WinPmem (Windows Memory Acquisition)

```bash
# Dump physical memory to raw file
winpmem_mini_x64.exe memory.raw

# Dump to AFF4 format (compressed, with metadata)
winpmem_mini_x64.exe -o memory.aff4

# Dump specific address range
winpmem_mini_x64.exe --mode physical -o memory.raw

# Dump with page file included
winpmem_mini_x64.exe -p pagefile.sys -o memory_with_pagefile.raw

# Verify acquisition
certutil -hashfile memory.raw SHA256
```

### Remote Memory Capture

```bash
# Remote memory acquisition via SSH (Linux target)
ssh root@target "insmod /tmp/lime.ko 'path=tcp:4444 format=lime'" &
nc target 4444 > remote_memory.lime

# Remote memory acquisition via WinRM (Windows target)
# Upload winpmem and execute remotely
Invoke-Command -ComputerName target -ScriptBlock { C:\temp\winpmem.exe C:\temp\mem.raw }
Copy-Item -Path \\target\C$\temp\mem.raw -Destination .\evidence\

# AVML (Acquire Volatile Memory for Linux) - no kernel module needed
./avml memory.lime
./avml --compress memory.lime.zst

# Capture memory from VMware virtual machine
vmss2core -W virtual_machine.vmss virtual_machine.vmem
# Or directly copy .vmem file while VM is running

# Capture memory from VirtualBox
VBoxManage debugvm "VM_Name" dumpvmcore --filename=memory.elf
```

---

## 12. Volatility3 Analysis

### Process Analysis

```bash
# List running processes
vol3 -f memory.raw windows.pslist.PsList
vol3 -f memory.raw windows.pstree.PsTree

# Detect hidden processes (compare multiple sources)
vol3 -f memory.raw windows.psscan.PsScan

# Process command line arguments
vol3 -f memory.raw windows.cmdline.CmdLine

# Process environment variables
vol3 -f memory.raw windows.envars.Envars --pid 1234

# DLL listing for specific process
vol3 -f memory.raw windows.dlllist.DllList --pid 1234

# Process memory map
vol3 -f memory.raw windows.memmap.Memmap --pid 1234 --dump
```

### Network Connection Analysis

```bash
# Active network connections
vol3 -f memory.raw windows.netscan.NetScan

# Filter for established connections
vol3 -f memory.raw windows.netscan.NetScan | grep ESTABLISHED

# Filter for listening ports
vol3 -f memory.raw windows.netscan.NetScan | grep LISTENING

# Linux network connections
vol3 -f memory.lime linux.sockstat.Sockstat

# Identify suspicious outbound connections (non-standard ports)
vol3 -f memory.raw windows.netscan.NetScan | awk '$4 !~ /:80$|:443$|:53$/ && $6 == "ESTABLISHED"'
```

### Malware Detection

```bash
# Detect injected code (RWX memory regions)
vol3 -f memory.raw windows.malfind.Malfind

# Dump suspicious process memory for analysis
vol3 -f memory.raw windows.malfind.Malfind --dump --pid 1234

# Check for API hooks
vol3 -f memory.raw windows.ssdt.SSDT

# Scan for known malware signatures with YARA
vol3 -f memory.raw windows.vadyarascan.VadYaraScan --yara-file malware_rules.yar

# Registry analysis (persistence mechanisms)
vol3 -f memory.raw windows.registry.printkey.PrintKey --key "Software\Microsoft\Windows\CurrentVersion\Run"

# Extract handles (files, registry keys, mutexes)
vol3 -f memory.raw windows.handles.Handles --pid 1234
```

### Volatility3 Linux Analysis

```bash
# Linux process listing
vol3 -f memory.lime linux.pslist.PsList
vol3 -f memory.lime linux.pstree.PsTree

# Linux bash history from memory
vol3 -f memory.lime linux.bash.Bash

# Linux loaded kernel modules (detect rootkits)
vol3 -f memory.lime linux.lsmod.Lsmod

# Linux mount points
vol3 -f memory.lime linux.mountinfo.MountInfo

# Linux network connections
vol3 -f memory.lime linux.sockstat.Sockstat

# Check for LD_PRELOAD rootkits
vol3 -f memory.lime linux.envars.Envars | grep LD_PRELOAD
```

---

## 13. Disk Forensics

### DD Imaging with Verification

```bash
# Create forensic image with dcfldd (enhanced dd)
dcfldd if=/dev/sdb of=evidence.dd bs=4K hash=sha256 hashlog=hash.log hashwindow=1G

# Create split image (for large disks)
dcfldd if=/dev/sdb of=evidence.dd.split bs=4K split=2G hash=sha256

# Create E01 (Expert Witness) format image with ewfacquire
ewfacquire /dev/sdb -t evidence -f encase6 -c deflate:best -S 2G

# Mount E01 image for analysis
ewfmount evidence.E01 /mnt/ewf/
mount -o ro,loop /mnt/ewf/ewf1 /mnt/evidence/

# Verify image integrity
dcfldd if=evidence.dd hash=sha256 hashlog=verify.log
diff hash.log verify.log

# Create image over network (avoid writing to evidence disk)
ssh root@target "dd if=/dev/sda bs=4K" | dd of=remote_evidence.dd bs=4K
```

### File Carving and Recovery

```bash
# Foremost - recover files by header/footer signatures
foremost -t jpg,png,pdf,doc,xls,zip -i evidence.dd -o /recovery/

# PhotoRec - advanced file recovery
photorec /d /recovery/ evidence.dd

# Scalpel - configurable file carving
scalpel -c /etc/scalpel/scalpel.conf -o /recovery/ evidence.dd

# Bulk Extractor - extract artifacts (emails, URLs, credit cards)
bulk_extractor -o /output/ evidence.dd
# Review: email.txt, url.txt, ccn.txt, telephone.txt

# Recover deleted files from ext4 filesystem
extundelete evidence.dd --restore-all --output-dir /recovery/

# Recover deleted files from NTFS
ntfsundelete /dev/sdb1 -u -m '*.docx' -d /recovery/
```

### Deleted File Recovery and Slack Space

```bash
# List deleted files in filesystem
fls -rd -o 2048 evidence.dd

# Recover specific deleted file by inode
icat -o 2048 evidence.dd 12345 > recovered_file.doc

# Extract file slack space (data between EOF and end of cluster)
blkls -s evidence.dd > slack_space.raw
strings slack_space.raw | grep -iE "password|secret|key"

# Search unallocated space for keywords
blkls evidence.dd > unallocated.raw
grep -boa "password" unallocated.raw

# Recover deleted partitions
testdisk evidence.dd
# Interactive: Analyze -> Quick Search -> Write partition table
```

### Filesystem Timeline Generation

```bash
# Generate body file from filesystem
fls -r -m "/" -o 2048 evidence.dd > body.txt

# Create timeline from body file
mactime -b body.txt -d > timeline.csv

# Filter timeline by date range
mactime -b body.txt -d "2026-01-01..2026-01-31" > january_timeline.csv

# Generate NTFS-specific timeline (includes $MFT metadata)
analyzeMFT.py -f \$MFT -o mft_timeline.csv -e

# Combine multiple timeline sources
cat body_disk1.txt body_disk2.txt > combined_body.txt
mactime -b combined_body.txt -d > combined_timeline.csv
```

---

## 14. Log Analysis

### Windows Event Log Analysis

```bash
# Parse Windows Event Logs with evtx_dump
evtx_dump.py Security.evtx > security_events.xml

# Search for logon events (Event ID 4624)
evtx_dump.py Security.evtx | grep -A 20 "EventID.*4624"

# Search for failed logons (Event ID 4625)
evtx_dump.py Security.evtx | grep -A 20 "EventID.*4625" | grep -E "TargetUserName|IpAddress"

# Search for new service installations (Event ID 7045)
evtx_dump.py System.evtx | grep -A 15 "EventID.*7045"

# Search for PowerShell execution (Event ID 4104)
evtx_dump.py Microsoft-Windows-PowerShell%4Operational.evtx | grep -A 30 "EventID.*4104"

# Detect log clearing (Event ID 1102)
evtx_dump.py Security.evtx | grep -A 10 "EventID.*1102"
```

### Syslog Parsing and Analysis

```bash
# Parse auth.log for SSH brute force
grep "Failed password" /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -20

# Detect successful SSH logins after failed attempts
grep "Accepted" /var/log/auth.log | awk '{print $1,$2,$3,$9,$11}'

# Parse Apache/Nginx logs for suspicious requests
awk '$9 >= 400' /var/log/apache2/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20

# Detect SQL injection attempts in web logs
grep -iE "union.*select|or.*1=1|drop.*table|insert.*into" /var/log/apache2/access.log

# Detect command injection attempts
grep -iE ";\s*(ls|cat|id|whoami|wget|curl)" /var/log/apache2/access.log

# Parse syslog for privilege escalation indicators
grep -iE "sudo|su\[|pkexec|polkit" /var/log/auth.log | grep -v "session opened"
```

### Timeline Construction from Multiple Sources

```bash
# Combine filesystem, log, and network timelines
# Step 1: Generate filesystem timeline
fls -r -m "/" evidence.dd > body.txt
mactime -b body.txt -d > fs_timeline.csv

# Step 2: Parse logs into timeline format
awk '{print $1" "$2" "$3",LOG,"$0}' /var/log/auth.log > log_timeline.csv

# Step 3: Parse network capture timestamps

<!-- truncated for token budget; see external/kali-claw for the rest -->

