# command-injection-advanced

# Skill: Advanced Command Injection

> **Supplementary Files**:
> - `payloads.md` -- Injection payloads organized by 10 categories (OS command basics, filter bypass, LDAP injection, NoSQL injection, template injection, XPath injection, encoding/obfuscation, context-specific, blind injection, CyberGym templates)
> - `test-cases.md` -- Structured test cases with severity levels (6 test cases covering command injection bypass, LDAP auth bypass, NoSQL injection, SSTI RCE, XPath injection, template engine exploitation)
> - `guides/command-injection-filter-bypass.md` -- Comprehensive filter bypass techniques (space bypass, keyword bypass, encoding tricks)
> - `guides/ldap-nosql-injection-guide.md` -- LDAP filter injection and MongoDB/Redis exploitation
> - `guides/ssti-exploitation-guide.md` -- Template injection for RCE (Jinja2/Thymeleaf/FreeMarker)
> - `guides/blind-injection-techniques.md` -- Time-based, DNS exfil, HTTP callbacks, error-based

## Summary

Advanced Command Injection skill domain covering web attack operations beyond SQL injection.

**Tools**: commix, Burp Suite, ldapsearch, nosqli, tplmap, sqlmap, payload generators, filter analyzers, encoding scripts, callback servers

**Domain**: web-attack

**OWASP**: A03:2021-Injection

**MITRE ATT&CK**: TA0002-Execution

## Description

Advanced injection attacks expand beyond SQL to target diverse interpreters and execution engines across web applications. This skill covers OS command injection (shell command execution), LDAP injection (authentication bypass), NoSQL injection (MongoDB/Redis exploitation), template injection (SSTI for RCE), XPath injection (XML data extraction), and comprehensive filter bypass techniques.

**Six Core Injection Types**:

- **OS Command Injection**: Malicious shell commands are injected into application parameters that invoke system commands. Exploitation leverages command separators (`;`, `|`, `&&`, `||`), command substitution (`` ` ``, `$()`), and filter bypass techniques (IFS, encoding, null bytes). Target impact: arbitrary code execution, file system access, network pivoting.

- **LDAP Injection**: User-controlled input is inserted into LDAP queries without proper escaping. Attackers manipulate filters using wildcards (`*`), boolean operators (`&`, `|`), and parentheses to bypass authentication or extract directory data. Commonly found in enterprise login portals and directory search features.

- **NoSQL Injection**: Targets document databases (MongoDB) and key-value stores (Redis) that use JSON, JavaScript, or custom query languages. Exploits operator injection (`$where`, `$ne`, `$gt`), JavaScript eval contexts, and command execution primitives (Redis `EVAL`, `SCRIPT`). Can lead to authentication bypass, data exfiltration, or RCE.

- **Template Injection (SSTI)**: Server-Side Template Injection occurs when user input is embedded directly into template engines (Jinja2, Thymeleaf, FreeMarker, Pug) without sanitization. Attackers leverage template syntax to access internal objects, invoke methods, and achieve remote code execution through expression evaluation.

- **XPath Injection**: Malicious XPath syntax is injected into XML queries, allowing attackers to bypass authentication, extract node data, or traverse document structure. Similar to SQL injection but targets XML databases and XML-based authentication systems.

- **Filter Bypass Techniques**: Advanced methods to evade input validation, WAFs, and blacklist filters - including space bypass (`${IFS}`, `$IFS$9`, tabs), keyword bypass (string concatenation, wildcards, case manipulation), encoding (URL, Unicode, hex, octal, base64), and context-specific tricks (bash brace expansion, PowerShell obfuscation).

**Attack Surface**: Web forms, API parameters, HTTP headers, file upload handlers, template renderers, authentication systems, search interfaces, configuration panels, CI/CD pipelines, serverless functions.

## Use Cases

1. **Web Application Penetration Testing**: Systematically probe command execution points (ping utilities, file processors, system tools), LDAP authentication interfaces, NoSQL query endpoints, and template renderers. Construct payloads to demonstrate exploitability and measure impact scope.

2. **Bug Bounty Hunting**: Identify injection vulnerabilities in modern web stacks - serverless functions (AWS Lambda), container orchestration APIs, CI/CD webhooks, GraphQL resolvers, and microservice backends. Focus on high-value targets like authentication bypass and RCE chains.

3. **CyberGym Challenge Solving**: Target IN1-IN4 bug classes with filter-aware payloads, blind injection techniques, and multi-stage exploitation chains. Adapt to restricted environments with encoding obfuscation and protocol-level manipulation.

4. **Security Code Audit**: Review application code for unsafe command construction (`os.system()`, `subprocess.call()`), LDAP query builders, NoSQL query objects, template rendering logic, and XPath evaluators. Identify missing input validation and output encoding.

5. **Red Team Operations**: Chain injection vulnerabilities with other attack vectors - SSRF to internal services, file upload to webshell, SSTI to reverse shell, LDAP injection to credential theft. Build multi-stage payloads for defense evasion and persistence.

6. **Filter and WAF Bypass Research**: Analyze blacklist patterns, encoding normalization bugs, and parser differentials. Develop bypass techniques for commercial WAFs (ModSecurity, CloudFlare, AWS WAF) and custom input filters.

---

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **commix** | Automated OS command injection detection and exploitation | `commix -u "http://target/ping?host=127.0.0.1" --batch --technique=TFBSC` |
| **Burp Suite** | HTTP interception, parameter tampering, injection testing, payload encoding | Repeater: modify POST body to inject SSTI payload |
| **ldapsearch** | LDAP query testing and filter manipulation | `ldapsearch -x -H ldap://target -b "dc=example,dc=com" "(uid=admin*)"` |
| **nosqli** | NoSQL injection scanner for MongoDB, CouchDB | `python nosqli-scan.py -t http://target/api/login -p username,password` |
| **tplmap** | Template injection detection and exploitation (Jinja2, Mako, etc.) | `python tplmap.py -u "http://target/view?name=test"` |
| **sqlmap** | Multi-purpose injection tool (supports OS command via `--os-cmd`) | `sqlmap -u "URL" --os-shell --technique=E` |
| **payload generators** | Custom script tools for encoding, obfuscation, format conversion | `python3 bypass-generator.py --payload "cat /etc/passwd" --encoding url,hex` |
| **filter analyzers** | Blacklist detection and bypass suggestion tools | `python3 filter-probe.py --target http://target/exec --wordlist keywords.txt` |
| **encoding scripts** | Hex, octal, Unicode, base64 encoding utilities | `echo "id" \| xxd -p` (hex), `printf '\\x69\\x64'` (octal) |
| **callback servers** | Out-of-band detection (DNS exfil, HTTP callbacks) | Burp Collaborator, interact.sh, webhook.site |

Auxiliary tools: **CyberChef** (multi-stage encoding), **Hackvertor** (Burp encoding plugin), **parameth** (parameter discovery), **Arjun** (hidden parameter scanner), **ffuf** (fuzzing), **wfuzz** (payload iteration).

---

## Methodology

### Attack Chain

```
[1] Input Point             [2] Injection Testing      [3] Filter Bypass
    Discovery                  - Syntax probes            - Encoding obfuscation
  - Command execution          - Context analysis         - Keyword alternatives
  - LDAP authentication        - Error message analysis   - Space/separator tricks
  - NoSQL query endpoints      - Behavior comparison      - Null byte injection
  - Template renderers              |                         |
  - XPath evaluators               v                         v
       |                      [4] Exploitation          [5] Post-Exploitation
       v                        - RCE payload delivery    - Reverse shell upgrade
  Authentication bypass          - Data exfiltration       - Credential harvesting
  Data extraction                - Privilege escalation    - Lateral movement
  Service enumeration            - Blind injection         - Persistence mechanisms
```

**Stage 1: Input Point Discovery**
- **Command execution surfaces**: Network utilities (ping, traceroute, nslookup), file processors (ImageMagick, FFmpeg), backup/restore functions, system info panels
- **LDAP injection points**: Login forms with AD/LDAP backend, directory search, employee lookup, SSO authentication
- **NoSQL endpoints**: REST APIs with JSON bodies, GraphQL queries, search filters, aggregation pipelines
- **Template contexts**: Email templates, PDF generators, markdown renderers, CMS themes, report builders
- **XPath targets**: XML-based authentication, SOAP APIs, RSS/Atom feed parsers, configuration file processors

**Stage 2: Injection Testing**
- **OS command probes**: Test command separators (`;`, `|`, `&&`, `||`), command substitution (`` ` ``, `$()`), and basic syntax variations
- **LDAP filter tests**: Test wildcard patterns, boolean operators (`*`, `&`, `|`), and parenthesis manipulation
- **NoSQL operator injection**: Test database-specific operators like comparison operators and regex patterns
- **SSTI detection**: Test mathematical expressions with multiple template syntaxes to identify engine
- **XPath syntax**: Test boolean logic, string functions, and XML node traversal

**Stage 3: Filter Bypass**
- **Space bypass**: Test alternative whitespace characters, bash parameter expansion, and file input redirection techniques
- **Keyword bypass**: Test quote insertion, case manipulation, character classes, and string concatenation via variable expansion
- **Encoding chains**: Test URL encoding, hex encoding, octal encoding, and base64 decoding in subshells
- **Context-specific tricks**: Test bash brace expansion, PowerShell obfuscation, and interpreter-specific syntax
- **Null byte injection**: Test null byte truncation for command-line filters

**Stage 4: Exploitation**
- **OS command RCE**: Use command substitution to execute arbitrary shell commands, establish reverse shells via network protocols
- **LDAP auth bypass**: Manipulate filter logic to bypass authentication checks, extract user attributes via boolean-based blind injection
- **NoSQL RCE**: Leverage JavaScript eval contexts in document databases, chain injection with server-side script execution
- **SSTI RCE (multi-engine)**: Access internal object hierarchies, import dangerous modules, execute system commands via template syntax
- **XPath data extraction**: Use XPath functions (substring, contains, starts-with) for binary search data extraction

**Stage 5: Post-Exploitation**
- Upgrade to interactive shell (Python pty, script pty)
- Harvest credentials from environment variables, config files, databases
- Pivot to internal services (SSH, databases, admin panels)
- Establish persistence (cron jobs, startup scripts, backdoor accounts)

### 1. OS Command Injection

#### Filter Bypass - Space Replacement

Use **commix** tool for automated space bypass detection, or apply manual techniques:
- Internal Field Separator (IFS) variable expansion in bash
- Alternative whitespace characters (tab, newline, form feed)
- Brace expansion without spaces (bash-specific)
- Input redirection operators without spaces

#### Filter Bypass - Keyword Evasion

Bypass blacklist filters using:
- Quote insertion (empty quotes between characters)
- Backslash escaping of individual characters
- Variable expansion with empty or controlled values
- Wildcard and glob patterns
- Base64 encoding with decoding in subshells

#### Advanced Techniques

Use automated tools:
- **commix**: Automated OS command injection detection with multiple techniques
- **Blind detection**: Time-based delays or out-of-band callbacks via DNS/HTTP
- **Data exfiltration**: Use DNS queries, HTTP requests, or file I/O for blind injection confirmation

---

### 2. LDAP Injection

#### Authentication Bypass

LDAP filter syntax uses boolean logic (`&` for AND, `|` for OR) and wildcards (`*`). Injection manipulates these operators.

**Techniques**:
- Wildcard injection to match any user
- Boolean operator injection to create tautologies
- Closing parenthesis bypass to manipulate filter structure
- Attribute-based matching to bypass password verification

#### Data Extraction via Blind Injection

```bash
# Length enumeration - determine attribute length
username: admin)(|(uid=*  # Always true
username: admin)(|(uidNumber>=1000)  # Test numeric ranges

# Binary search for specific characters
# If "a" is first character of sn (surname):
username: admin)(|(sn=a*)  # True if starts with "a"
username: admin)(|(sn=b*)  # False if doesn't start with "b"

# Enumerate all users
ldapsearch -x -H ldap://target -b "dc=example,dc=com" "(uid=*)"

# Extract specific attributes
ldapsearch -x -H ldap://target -b "dc=example,dc=com" "(uid=admin)" sn mail telephoneNumber
```

#### LDAP Injection Testing Tools

```bash
# Manual testing with curl (HTTP to LDAP bridge)
curl -X POST http://target/login \
  -d "username=admin*)(%26(uid=*&password=test"

# Automated scanning
ldapdomaindump ldap://target -u 'DOMAIN\user' -p 'password'

# Fuzzing LDAP filters
wfuzz -c -z file,ldap-injections.txt \
  "http://target/search?query=FUZZ"
```

---

### 3. NoSQL Injection

#### MongoDB Operator Injection

NoSQL databases use operators for query construction instead of SQL syntax.

**Techniques**:
- Comparison operators to match any value without password verification
- Regex operators for pattern-based username enumeration
- Field existence checks
- JavaScript eval clauses (if enabled in configuration)

**Tool**: Use `nosqlmap` for automated operator detection and exploitation.

#### Redis Command Injection

Redis Lua scripting via EVAL command can execute system commands.

**Concept**: Chain Lua script execution with system command primitives.


<!-- truncated for token budget -->

