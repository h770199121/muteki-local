# web-ssrf

# Skill: SSRF serviceendrequestforgery / Server-Side Request Forgery

> **Supplementary Files**:
> - `payloads.md` — SSRF attack payload allset：basic detect、protocolsmuggling、cloud metadatadata extraction、bypasstechnique、DNS rebinding、blind SSRF、RCE groupcombinechain
> - `test-cases.md` — structureizetestinguseexamplechecklist，cover SSRF Detect、internal networkScan、cloud metadatadata、bypasstechnique、advanced exploit，with severelevelother

## Summary

Web Ssrf skill domain covering web attack operations.

**Tools**: Burp Suite, curl, ffuf, Gopherus, SSRFmap, Burp Collaborator

**Domain**: web-attack

**OWASP**: A10:2021-SSRF

**MITRE ATT&CK**: T1190-Exploit Public-Facing App

## Description

Server-Side Request Forgery (SSRF) attacks including basic, blind, and advanced bypass techniques, internal port scanning, cloud metadata extraction (AWS/GCP/Azure), protocol smuggling (gopher://, dict://, file://), and chained RCE exploitation. Also covers defense strategies: URL allowlisting, IP range validation, protocol restrictions, and cloud metadata protection.

**Agent canpowerstatement**: already complete OWASP Top 10 2025 SSRF complete learning，masterautomated SSRF ScanTooldevelopmentandcloud metadatadata extractionToolchain。

## Use Cases / Use Cases

1. **Web applicationpenetration testing** - Detecttargetapplicationin URL obtain、fileimport、Webhook etc.successcan SSRF vulnerability，exploititsaccessinternalresource
2. **cloudenvironmentsecurity assessment** - through SSRF Extract AWS/GCP/Azure realexamplemetadata，obtaintemporarywhen credentialsandsensitiveconfigurationinformation
3. **Internal network penetration pivot** - Exploit SSRF as a pivot to scan internal network service ports, access internal APIs, and detect Kubernetes/Docker and other infrastructure.
4. **CTF competition challenges** - Quickly identify SSRF challenge types; construct protocol smuggling, DNS rebinding, IP encoding bypass, and other advanced payloads.
5. **security code audit** - fromDefense Perspectivereview URL handlinglogic，assessmentfilter bypassrisk，realimplementpartlayerdefensesolution

## Core Tools / Core Tools

| Tool | Purpose | Command Example |
|------|------|----------|
| **Burp Suite** | interceptmodify HTTP request，construct SSRF payload，testing redirect bypass | Repeater moduledebug `?url=http://169.254.169.254/` |
| **curl** | quick testing SSRF payload，verifycloud metadatadataendpoint | `curl "http://target/fetch?url=http://127.0.0.1:8080/admin"` |
| **ffuf** | fuzzytesting URL parameter，batchamountdetectinternal network IP andport | `ffuf -u "http://target/fetch?url=http://FUZZ:FUZ2Z" -w ips.txt -w ports.txt` |
| **Gopherus** | generate gopher:// protocol payload，exploit Redis/MySQL/FASTCGI etc. | `python3 gopherus.py --exploit redis` |
| **SSRFmap** | automated SSRF Detectandexploitframework，supportsmultiplekindattackmodule | `python3 ssrfmap.py -r request.txt -p url -m readfiles` |

## Methodology / Methodology

### Attack Chain / Attack Chain

```
URL 参数发现 → 协议走私 → 内网扫描 → 云元数据提取 → RCE 组合链
```

**1. URL parameterdiscovery (Discovery)**
- Identifyaccept URL parameter：`url=`、`path=`、`src=`、`dest=`、`redirect=`、`callback=`
- testing Webhook、PDF generate、imageload、fileimportetc.successcanpoint
- use Burp Suite Hunter or ffuf automated discoveryhideparameter

**2. protocolsmuggling (Protocol Smuggling)**
- `file:///etc/passwd` - readlocalfile
- `gopher://host:port/_DATA` - sendarbitrary TCP data（Redis/MySQL/SMTP）
- `dict://host:port/COMMAND` - executedictionaryprotocolcommand
- `ldap://host:port/` - LDAP query
- `http/https` - standard HTTP requesttointernalservice

**3. internal networkScan (Internal Network Scanning)**
- Scancommon internal networknetworksegment：`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`
- detectcommon port：22、80、443、3306、5432、6379、8080、8443、9200、27017
- exploitresponsewhen intervaldifferencejudgeportopenstatus（blind SSRF）

**4. cloud metadatadata extraction (Cloud Metadata Extraction)**
- AWS: `http://169.254.169.254/latest/meta-data/iam/security-credentials/`
- GCP: `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token`
- Azure: `http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01`
- obtaintemporarywhen credentialsafterlateral movementtoitsothercloudresource

**5. RCE groupcombinechain (RCE Chain)**
- SSRF + Redis not authorization: `gopher://127.0.0.1:6379/_CONFIG SET dir /var/www/html` write Webshell
- SSRF + MySQL: `gopher://127.0.0.1:3306/` construct MySQL protocolpackageexecute SQL
- SSRF + FASTCGI: construct FastCGI protocolpackageexecutearbitrarycode
- SSRF + AWS IAM: obtaintemporarywhen credentialsafterthrough AWS CLI takeovercloudresource

## Practical Steps / Practical Steps

### Step 1: basic SSRF Detect
testing loopback addresses (`127.0.0.1`, `localhost`) and file protocol (`file:///etc/passwd`); combine with IP address transformations (hexadecimal, decimal, IPv6, octal, all-zero) to bypass basic filters.

### Step 2: cloud metadatadata extraction
Extract AWS IAM rolecredentials、GCP Service Account Token、Azure Managed Identity Token，use IP transformationbypasscloud metadatadataaddressfilter。

### Step 3: protocolsmugglingexploit
Exploit `gopher://` protocol to manipulate Redis/MySQL, `dict://` to detect service versions, `file://` to read server sensitive files.

### Step 4: advanced bypasstechnique
Open Redirect exploit、`@` characternumberspoofing、DNS rebinding、URL encoding bypass、URL solveanalysisdifferenceexploit。

### Step 5: automated SSRF Scan
use SSRFmap automated Detect（readfiles/awsmetadata/portscan module），ffuf batchamountScaninternal networkport，Burp Collaborator Detectblind SSRF。

> **See payloads.md for detailed payloads, and test-cases.md for complete test checklist。**

## Defense Evasion Techniques

Evade SSRF detection by: using DNS rebinding to bypass IP-based blocklists (the DNS lookup returns an allowed IP, then resolves to the target IP on the actual request), encoding IP addresses in decimal/hex/octal formats to bypass string-matching filters, using URL parser inconsistencies (e.g., `http://evil.com#@safe.com` where different parsers disagree on the hostname), and leveraging open redirects on trusted domains to chain through an allowed host to the internal target. For cloud metadata, use IP representations of 169.254.169.254 that may not be in the blocklist.

## Advanced Techniques

Advanced SSRF exploitation includes: HTTP request smuggling combined with SSRF to bypass frontend proxy restrictions, DNS rebinding with precise timing to win race conditions between DNS resolution and application request, SSRF through HTTP headers (Host, X-Forwarded-For, Referer) that get reflected into backend requests, exploiting PDF generators and image processors that fetch external resources, and chaining SSRF with server-side template injection for full code execution. For Kubernetes environments, explore SSRF targeting the cloud metadata service to steal pod service account tokens.
