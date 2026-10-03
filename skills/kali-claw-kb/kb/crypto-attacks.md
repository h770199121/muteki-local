# crypto-attacks

# Skill: Cryptographic Attacks

> **Supplementary Files**:
> - `payloads.md` — Cryptographic attack payload collection: weak algorithm detection, hash cracking, Padding Oracle, Hash Length Extension, ECB mode, JWT attacks, RSA attacks, SSL/TLS test commands
> - `test-cases.md` — Structured test cases: complete test checklist covering cryptographic detection, hash cracking, protocol attacks, JWT attacks, and advanced techniques

## Summary

Crypto Attacks skill domain covering cryptography operations.

**Tools**: openssl, sslscan, testssl.sh, hashcat, CyberChef, padbuster, RsaCtfTool

**Domain**: cryptography

**OWASP**: A04:2021-Cryptographic Failures

## Description

Cryptographic Attacks target implementation flaws and algorithm weaknesses in encryption systems, covering OWASP A04: Cryptographic Failures. Attackers do not break mathematical problems; instead, they exploit engineering implementation errors: weak algorithm remnants (RC4/DES/MD5/SHA1), key management mistakes (hardcoded/reused/non-rotated), encryption mode misuse (ECB/Padding Oracle/IV Reuse), protocol downgrade (SSLv3/TLS 1.0), and missing signature verification (JWT alg:none/Algorithm Confusion).

**Core Insight**: The mathematical foundations of modern cryptography are robust — attackers almost never "break encryption algorithms" but rather "break how encryption is used." A rule of thumb: if you feel like you are attacking the math, you are probably heading in the wrong direction; instead, look for who wrote the key in the code, which IV is fixed, which service still accepts SSLv3.

**Key Attack Surfaces**:

- **Weak Algorithms**: RC4 (fully broken), DES (56-bit brute forceable), MD5/SHA1 (collision attacks), Blowfish (64-bit block)
- **Key Management Flaws**: Hardcoded keys, fixed IVs, key reuse, no key rotation, keys stored in source code/config files
- **Padding Oracle**: Server returns different responses for decryption padding errors, allowing attackers to recover plaintext byte by byte without the key
- **Hash Length Extension**: Hash functions based on Merkle-Damgard construction (SHA-1/MD5) allow appending data to MAC without knowing the key
- **SSL/TLS Vulnerabilities**: POODLE (SSLv3), BEAST (TLS 1.0 CBC), Heartbleed (OpenSSL), certificate verification bypass

---

## Use Cases

1. **Web Application Encryption Audit** - Detect HTTPS configuration flaws, cookie encryption weaknesses, missing API signature verification, sensitive data transmitted in plaintext
2. **JWT / Token Security Testing** - Algorithm confusion attacks (RS256 -> HS256), alg:none bypass, key brute force, payload tampering
3. **CTF Cryptography Challenges** - Quickly identify encryption modes (ECB/CBC/CTR), known plaintext attacks, Padding Oracle, hash extension attacks
4. **Data Breach Assessment** - Analyze whether leaked data uses weak encryption, assess cracking feasibility (hash type/salt/iterations)
5. **TLS/SSL Configuration Hardening** - Scan server-supported protocol versions, cipher suites, certificate chain validity

---

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **openssl** | Certificate analysis, protocol testing, encryption/decryption operations | `openssl s_client -connect target:443 -tls1` |
| **sslscan** | Quick TLS configuration scan, detect supported protocols and cipher suites | `sslscan target.com` |
| **testssl.sh** | Comprehensive SSL/TLS security audit, 200+ checks | `testssl.sh --full target.com` |
| **hashcat** | Offline hash cracking (including JWT key brute force mode 16500) | `hashcat -m 16500 jwt.txt rockyou.txt` |
| **CyberChef** | Encoding/decoding/encryption/hashing online analysis (identify unknown encodings) | Browser tool, drag-and-drop operation |
| **padbuster** | Automated Padding Oracle attacks | `padbuster URL ENC_BLOCK 8` |

Auxiliary tools: **hash-identifier** (hash type identification), **htlea** (Hash Length Extension), **RsaCtfTool** (RSA attack collection), **jwt_tool** (full JWT testing workflow).

---

## Methodology

### Attack Chain

```
[1] Crypto ID            [2] Algorithm Analysis    [3] Key/IV Attacks
  - Protocol version       - Weak algorithm detect   - Hardcoded key search
  - Cipher suite enum      - Block size/mode detect  - IV predictability
  - Hash type ID           - Key length assessment   - Key reuse detection
  - Token format parse     - Padding mode analysis   - ECB mode detection
       |                        |                        |
       v                        v                        v
[4] Protocol Downgrade    [5] Data Decryption       [6] Signature Bypass
  - TLS version downgrade   - Padding Oracle          - JWT alg:none
  - Cipher suite downgrade  - Known plaintext attack  - Algorithm Confusion
  - Forward secrecy test    - Bit flipping attack     - Key brute force
  - Cert chain validation   - Hash extension attack   - Replay attacks
```

### Post-Quantum Migration

The post-quantum transition expands the crypto-attacks attack surface on three new axes that any Distinguished-tier engagement must cover: (a) classical-vs-quantum threat model, (b) hybrid construction correctness, and (c) protocol incompatibilities caused by larger PQ key / signature sizes. The attack chain below operationalizes the HNDL ("Harvest Now, Decrypt Later") adversary and the migration audit.

```
[PQM-1] Asset Inventory       [PQM-2] Algorithm Coverage   [PQM-3] Hybrid Construction
  - Long-lived keys cataloged   - FIPS 203/204/205 support     - X25519 + ML-KEM-768 KEM
  - HNDL exposure profiled      - liboqs / OQS-OpenSSL          - Transcript hash binding
  - PKI chain depth analyzed    - pqm4 (Cortex-M4 targets)      - KDF length-prefixing
       |                              |                                |
       v                              v                                v
[PQM-4] Protocol Compatibility [PQM-5] Downgrade Analysis   [PQM-6] PQC Implementation Audit
  - MTU / fragment / EDNS(0)    - Stripping PQ group             - KyberSlash (barrett div)
  - Middlebox cert handling     - Hybrid fallback policy         - Dilithium verify-before-release
  - X.509 alt-signature path    - Cipher string hardening        - Cross-protocol key reuse
```

**Real research touchpoints**: KyberSlash (2021), Injecting Crystals (Manganote et al., 2023), Crystal-Slinger, GROUNDTRUTH (2024), and Shor's algorithm assumptions about ECC/RSA recovery under a cryptographically relevant quantum computer (CRQC). The full attack taxonomy, parameter sizes, and lab procedures live in `guides/crypto-attacks-pqc-migration-side-channel.md`.

### Side-Channel Analysis

Side-channel analysis (SCA) targets physical and microarchitectural leakage of secret-dependent computation -- the single largest source of real-world breaks of mathematically sound algorithms. Padding Oracle, Heartbleed, and Spectre/Meltdown are all side channels; the same methodology scales to power, EM, timing, and fault channels on cryptographic hardware.

```
[SCA-1] Channel Selection     [SCA-2] Trace Acquisition     [SCA-3] Statistical Attack
  - Timing (dudect)              - ChipWhisperer + STM32F4      - SPA: single-trace op ID
  - Power (SPA / DPA / CPA)      - Riscure Inspector            - DPA: difference-of-means
  - Electromagnetic (EMA)        - Near-field EM probe + scope  - CPA: HW correlation
  - Cache-timing (Spectre)       - Remote latency measurement   - Template: max likelihood
       |                              |                                |
       v                              v                                v
[SCA-4] PQC-Specific Attacks   [SCA-5] Constant-Time Audit   [SCA-6] Fault Injection
  - Kyber compress leak          - dudect / ctgrind / binsec    - Clock / power glitch
  - Dilithium z-step             - HW-accel (AES-NI, ARMv8)     - Verify-before-release bypass
  - SPHINCS+ WOTS+ chain         - Masking (order-1 minimum)    - Fault-tolerant chains
```

**Equipment baseline**: ChipWhisperer Husky or Lite + CW308/STM32F4 target for power/EM/glitch; `dudect` / `ctgrind` for software constant-time verification; Riscure Inspector for enterprise-grade CPA / template attacks. Deep dive: `guides/crypto-attacks-pqc-migration-side-channel.md`.

### Crypto-Agility Framework

Crypto-agility is the ability to swap cryptographic primitives without code changes or protocol breakage -- the strongest predictor of whether a PQC migration will succeed. The framework below structures the audit; an organization that cannot answer "yes" to every row is non-agile and at risk during any future algorithm transition (PQC today, AES-GCM-SIV tomorrow, whatever comes next).

```
[CA-1] Algorithm Inventory      [CA-2] Pluggable Primitive API  [CA-3] Negotiation & Telemetry
  - Every long-term key mapped    - Algorithm as config string     - Negotiated group logged
  - Every signature location      - Key store holds 5 KB PQ keys   - Downgrade detected
  - Every TLS / SSH / IPsec       - No hardcoded constants         - Per-peer algorithm tracked
       |                                |                                |
       v                                v                                v
[CA-4] Swap Planning             [CA-5] Test Coverage            [CA-6] Rollback Readiness
  - 12-month / 24-month target    - ACVP / CAVP vectors            - Atomic rollback to classical
  - Hybrid (classical + PQ)       - Cross-stack interop tests       - Re-key without service outage
  - Pure-PQ end state             - Side-channel regression         - Root of trust migration
```

**Acceptance criterion**: a single configuration change in `crypto_policy.yaml` (e.g., `kem_group: x25519_mlkem768`) propagates to every endpoint, every library, every certificate, with no source modification -- and the change is observable in production telemetry within 24 hours. Anything less is non-agile.

#### PQC Migration and Side-Channel Mitigations

Beyond the row-level defenses, four structural mitigations cover the emerging PQ and side-channel surface:

1. **Hybrid-by-default for long-lived data**: any TLS / SSH / IPsec endpoint that protects data with a confidentiality lifetime of 10+ years MUST negotiate a hybrid group (e.g., `x25519_mlkem768`) and MUST reject ClientHello that strips the PQ group. Pure-PQ endpoints are acceptable only after the PQC primitive has accumulated 5+ years of adversarial analysis.
2. **Verify-before-release everywhere**: every PQC signature implementation must compute the signature, run a full verification under the public key, and retry on failure. This single step defeats the cheapest single-fault attacks (Injecting Crystals class) and is now mandated by FIPS 204.
3. **Constant-time as a CI gate, not a claim**: any "constant-time" assertion must be backed by automated `dudect` / `ctgrind` / `binsec` evidence in CI. Side-channel regression tests on cryptographic primitives must run on every commit, not as a release milestone. Hardware acceleration (AES-NI, ARMv8 SHA, dedicated PQ IP) is preferred over constant-time software where available.
4. **Crypto-agility first**: every algorithm must be expressible as a single configuration entry (cipher string, KEM group, signature OID), not a refactoring project. The acceptance test is "swap `x25519` to `x25519_mlkem768` in one config file; production telemetry reflects the change within 24 hours; no source modification." Organizations that cannot pass this test are non-agile and will not complete the PQC migration before the HNDL window closes.

---

## Practical Steps

### 1. Crypto Identification Phase

```bash
# SSL/TLS protocol scanning
testssl.sh --protocols target.com
sslscan target.com | grep -E "SSLv3|TLS 1.0|TLS 1.1"

# Hash type identification
hash-identifier
# Or: hashcat --identify hash.txt
```

### 2. Algorithm Analysis and Key Attacks

```bash
# Padding Oracle attack
padbuster http://target/page?data=ENC ENC 8 -encoding 0 -plaintext "admin=true"

# IV Reuse: Encrypt same plaintext twice, compare ciphertexts
```

### 3. Signature Bypass and Token Attacks

```bash
# JWT alg:none bypass
python3 jwt_tool.py <TOKEN> -X a

# JWT Algorithm Confusion (RS256 -> HS256)
python3 jwt_tool.py <TOKEN> -I -at HS256 -pc role -pv admin -k public_key.pem

# JWT key brute force
hashcat -m 16500 jwt_hash.txt /usr/share/wordlists/rockyou.txt
```

> **For detailed payloads see `payloads.md`, and for the complete test checklist see `test-cases.md`.**

---

## Detection and Evasion

Defenders can detect cryptographic attacks through several indicators: unusual TLS negotiation patterns (downgrade attempts logged by the server), repeated decryption errors in application logs (Padding Oracle attempts), JWT validation failures with algorithm mismatches, and anomalous hash cracking activity (high GPU utilization on compromised machines). Monitor certificate transparency logs for unauthorized certificate issuance. To evade detection during testing: spread JWT brute force attempts across multiple API endpoints, use timing delays in Padding Oracle attacks to avoid triggering rate limits, and test TLS downgrade resistance through a single well-crafted ClientHello rather than a noisy scan. For hash cracking, offload to dedicated GPU rigs outside the target network.

## Advanced Techniques

Beyond the core attacks, advanced cryptographic testing includes: RSA key recovery from partial key exposure (known bits of p or q), Bleichenbacher attacks against PKCS#1 v1.5 padding in RSA encryption, BEAST and Lucky13 attacks against TLS CBC cipher suites, hash length extension attacks against SHA-256 and SHA-512 (not just MD5/SHA1), and cryptographic side-channel attacks using timing analysis to extract secrets. For CTF challenges, practice with RsaCtfTool for automated RSA attack selection and CyberChef for rapid encoding/decoding chain prototyping.

## Defense Evasion Techniques

### TLS Fingerprint Mimicry

<!-- truncated for token budget -->

