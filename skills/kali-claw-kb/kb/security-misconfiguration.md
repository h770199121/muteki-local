# security-misconfiguration

## Summary

Security Misconfiguration skill domain covering defense operations.

**Tools**: Nmap, Nikto, testssl.sh, Burp Suite, WhatWeb

**Domain**: defense

**OWASP**: A02:2025-Misconfiguration

## Description

Security misconfiguration detection (OWASP A02:2025) covering default credentials, unnecessary services, verbose errors, missing security headers, and directory listing exposures across deployed systems. Misconfigurations are the most common and easily overlooked vulnerability class — not a tool flaw but a deployment and maintenance failure that degrades overall security posture.

**coreDetect domain**:
- **Default Credentials**: Default credentials not modified (admin/admin, root/root, test/test)
- **Unnecessary Services**: productionenvironmentlegacydebugport、managementinterface、exampleapplication
- **Verbose Errors**: stacktrackingleakagefilepath、databasetype、frameworkversion、SQL statement
- **Missing Security Headers**: missing X-Frame-Options、CSP、HSTS、X-Content-Type-Options etc.criticalprotectionhead
- **Directory Listing**: Web serverallowslistdirectorycontent，exposurebackupfile、configurationfile、databasedump

---

## Use Cases / Use Cases

1. **Web applicationpenetration testing** - fortargetperformcomprehensive configurationsecurity audit，discoveryexposure managementinterface、defaultinstallpage、sensitivefile
2. **Basic infrastructure security assessment** - Detect redundant services, open ports, default configuration
3. **TLS/SSL security audit** - assessmentcertificateconfiguration、protocolversion、passwordsetpiecestrongdegree
4. **cloudresourceconfigurationreview** - check S3 Bucket publicaccess、IAM policyoveratlenient、security grouprulenotwhen
5. **Compliance check** - Verify configuration against CIS Benchmark, OWASP ASVS standards

---

## Core Tools / Core Tools

| Tool | Purpose | Command Example |
|------|------|----------|
| **Nmap** | serviceEnumerate、versionDetect、scriptScan | `nmap -sV -sC --script=default,vuln target` |
| **Nikto** | Web serverconfigurationvulnerability scanning | `nikto -h http://target -o report.html -Format htm` |
| **testssl.sh** | TLS/SSL configurationcomprehensive Detect | `testssl.sh --full --quiet target:443` |
| **Burp Suite** | HTTP Header analysis、responsecheck、Scanner module | Proxy intercept -> check Response Headers -> Scanner maindynamicScan |
| **WhatWeb** | Web techniquefingerprinting、frameworkversionDetect | `whatweb -v http://target` |

Auxiliary tools: **curl** (manual header check), **Gobuster** (directory/file brute-force discovery), **Dirsearch** (directory enumeration), **Hydra** (default credential brute force), **ScoutSuite** (cloud configuration audit).

---

## Methodology / Methodology

### Attack Chain / Attack Chain

```
[1] Service Enumeration      [2] Default Credential Testing   [3] Header Analysis
    - nmap 版本探测              - 默认用户名/密码字典             - 检查安全 Header
    - whatweb 指纹识别            - Hydra/medusa 爆破              - CSP 策略审计
    - 端口与服务映射              - 管理接口默认凭证               - Cookie 属性检查
         |                           |                              |
         v                           v                              v
[4] Error Page Probing       [5] Config File Discovery
    - 触发详细错误响应            - 目录列表检测
    - 路径遍历探测                - 备份文件发现
    - 堆栈跟踪分析                - 版本控制文件暴露
    - 框架版本识别                - .env / .git / .svn 泄露
```

## Practical Steps / Practical Steps

### Step 1: Nikto Web Scan

use Nikto performautomated Web configurationScan，Detectdefaultfile、dangerousconfigurationandoverwhen component。

### Step 2: HTTP security Header check

obtainandreview HTTP response Header，verifycriticalsecurity Header iswhetherexistsandconfigurationcorrect。

### Step 3: defaultcredentialsbrute force

use Hydra forloginformanddatabaseserviceperformdefaultcredentialstesting。

### Step 4: Verbose Error exploit

throughsendmalformedrequest、superlengthparameter、illegal HTTP methodtriggerdetailed errorinformation。

### Step 5: directorylistandsensitivefilediscovery

Detectdirectorylistenablesituation，discoveryversioncontrolfileandenvironmentconfigurationfileleakage。

> **See payloads.md for detailed payloads, and test-cases.md for complete test checklist。**

---

## Defense Evasion Techniques

### Misconfiguration Exploitation Stealth
- **Use legitimate features**: Many misconfigs are legitimate features (e.g., public S3 for static hosting).
- **Off-hours abuse**: Exploit during low-traffic hours; less monitoring attention.
- **Distribute exploitation**: Spread across many accounts/sessions.

### Detection Bypass
- **CSPM rule exemptions**: Apply exemption tag (`CSPM-Exempt: true`); respected by some CSPM tools.
- **Use existing compliant resources**: Don't create new public bucket; abuse existing misconfigured one.
- **Cross-account resource sharing**: Share resource to attacker account via legitimate mechanism.

### Network Layer
- [ ] All unnecessary ports closed (only 80, 443 for web servers)
- [ ] Management interfaces (SSH, RDP, databases) restricted to internal IPs
- [ ] Firewall rules follow default-deny policy
- [ ] No services running on non-standard ports (scan all 65535 ports to verify)
- [ ] ICMP responses disabled where not needed

### Application Layer
- [ ] Debug mode disabled in production (`APP_DEBUG=false`, `DEBUG=False`, `display_errors=Off`)
- [ ] Default pages removed (Apache test page, Nginx default, Tomcat welcome)
- [ ] Default credentials changed on all services
- [ ] Directory listing disabled globally
- [ ] Custom error pages configured (no stack traces)
- [ ] Admin panels require authentication and IP restriction

### HTTP Security Headers
- [ ] `Strict-Transport-Security` (HSTS) with `includeSubDomains` and `preload`
- [ ] `Content-Security-Policy` with strict `default-src` and `script-src`
- [ ] `X-Content-Type-Options: nosniff`
- [ ] `X-Frame-Options: DENY` or `SAMEORIGIN`
- [ ] `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] `Permissions-Policy` restricting camera, microphone, geolocation

### TLS/SSL
- [ ] TLS 1.2 minimum; TLS 1.0 and 1.0 disabled
- [ ] Strong cipher suites only (no RC4, no DES, no 3DES)
- [ ] Certificate valid and not expired
- [ ] HSTS header present and configured
- [ ] Certificate chain complete (no missing intermediates)

### File and Data Protection
- [ ] `.git`, `.svn`, `.env` files not accessible via web
- [ ] Backup files (`.bak`, `.old`, `.sql`) not in web root
- [ ] Sensitive directories (`/admin`, `/backup`, `/config`) access-controlled
- [ ] Upload directories do not allow script execution
- [ ] No sensitive data in client-accessible JavaScript files

---

# config-audit.sh — Run automated configuration audit
TARGET="$1"
REPORT_DIR="reports/$(date +%Y%m%d)"

mkdir -p "$REPORT_DIR"

# Web server audit
nikto -h "https://$TARGET" -o "$REPORT_DIR/nikto.html" -Format htm

# TLS audit
testssl.sh --json-pretty "$TARGET:443" > "$REPORT_DIR/tls.json"

# Header audit (custom script)
curl -sI "https://$TARGET" | grep -iE "strict-transport|content-security|x-frame|x-content-type" \
  > "$REPORT_DIR/headers.txt"

# Nuclei misconfiguration templates
nuclei -u "https://$TARGET" -t misconfiguration/ -o "$REPORT_DIR/nuclei.txt"

echo "[+] Audit complete. Reports in $REPORT_DIR/"
```

---

# Baseline creation script
BASELINE_DIR="/opt/security-baselines/$(hostname)/$(date +%Y%m%d)"
mkdir -p "$BASELINE_DIR"

# Capture security-relevant configurations
cp /etc/apache2/apache2.conf "$BASELINE_DIR/" 2>/dev/null
cp /etc/nginx/nginx.conf "$BASELINE_DIR/" 2>/dev/null
cp /etc/ssh/sshd_config "$BASELINE_DIR/" 2>/dev/null
cp /etc/mysql/my.cnf "$BASELINE_DIR/" 2>/dev/null

# Capture security headers
curl -sI "https://$(hostname)" > "$BASELINE_DIR/security_headers.txt"

# Capture open ports
nmap -sT -O "$(hostname)" > "$BASELINE_DIR/open_ports.txt"

# Capture TLS configuration
testssl.sh --quiet "$(hostname):443" > "$BASELINE_DIR/tls_config.txt"

# Capture installed packages
dpkg -l > "$BASELINE_DIR/packages.txt" 2>/dev/null
rpm -qa > "$BASELINE_DIR/packages.txt" 2>/dev/null

echo "[+] Baseline saved to $BASELINE_DIR"
echo "[+] Run baseline-diff.sh to compare against this baseline"
```

```bash
#!/bin/bash
# Baseline comparison script
CURRENT="/tmp/current_baseline"
BASELINE="/opt/security-baselines/$(hostname)/latest"

# Create current snapshot (same commands as baseline creation)
# ... (same capture commands)

# Compare
echo "=== Security Header Changes ==="
diff "$BASELINE/security_headers.txt" "$CURRENT/security_headers.txt"

echo "=== Open Port Changes ==="
diff "$BASELINE/open_ports.txt" "$CURRENT/open_ports.txt"

echo "=== Package Changes ==="
diff "$BASELINE/packages.txt" "$CURRENT/packages.txt"
```
