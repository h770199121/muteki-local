# network-sniffing-mitm

# Skill: Network Sniffing and Man-in-the-Middle (MITM)

> **Supplementary Files**:
> - `payloads.md` — Attack payload collection: passive capture, ARP spoofing, DNS spoofing, credential harvesting, SSL stripping, caplet scripting, and traffic manipulation commands
> - `test-cases.md` — Structured test cases: TC-NSM-001 through TC-NSM-006 covering passive capture, ARP spoof MITM, responder credential harvest, bettercap caplets, DNS spoofing, and HTTPS downgrade

## Summary

Network Sniffing Mitm skill domain covering network attack operations.

**Tools**: wireshark/tshark, tcpdump, ettercap, bettercap, mitm6, responder, dsniff, driftnet (+2 more)

**Domain**: network-attack

**MITRE ATT&CK**: TA0006-Credential Access

## Description

Network Sniffing and MITM attacks focus on intercepting, analyzing, and manipulating network traffic between two communicating parties. This skill covers the full spectrum from passive packet capture (undetectable on shared media) through active man-in-the-middle positioning (ARP/NDP/DNS spoofing) to credential harvesting and traffic manipulation. The attacker positions themselves on the network path between victim and destination, enabling plaintext inspection of otherwise trusted communications.

**Core Insight**: MITM attacks exploit trust at Layer 2 and Layer 3 of the OSI model. ARP has no authentication, LLMNR/NBT-NS are fallback protocols that respond to any query, and IPv6 is often enabled by default with no security controls. These design assumptions create a wide attack surface on internal networks. A successful MITM position gives the attacker the same visibility as the network infrastructure itself.

**Key Attack Surfaces**:

- **ARP Protocol**: Stateless, unauthenticated — any host can claim any IP address by sending unsolicited ARP replies. Dynamic ARP Inspection (DAI) mitigates but is often not deployed.
- **LLMNR/NBT-NS/mDNS**: Windows fallback name resolution protocols broadcast queries when DNS fails. An attacker responds first and captures NTLM authentication hashes.
- **IPv6 SLAAC**: Windows prefers IPv6 over IPv4 by default. An attacker advertising a rogue IPv6 router becomes the preferred gateway without any IPv4 MITM.
- **DHCP**: Rogue DHCP servers hand out attacker-controlled DNS and gateway addresses to new clients on the network.
- **SSL/TLS Stripping**: Downgrading HTTPS to HTTP by rewriting URLs and stripping security headers before the client's first request reaches the server.
- **DNS Spoofing**: Responding to DNS queries with attacker-controlled IP addresses redirects victims to malicious services.

---

## Use Cases

1. **Internal Network Assessment** — Position between victim hosts and gateway to capture cleartext credentials (FTP, HTTP, SMTP, IMAP) and analyze protocol usage across the environment.
2. **Active Directory Credential Harvesting** — Poison LLMNR/NBT-NS/mDNS to collect NTLMv2 hashes from Windows clients, then crack offline or relay to other systems via SMB relay.
3. **Application Security Testing** — Intercept and modify HTTP/HTTPS traffic between a client and web application to test input validation, session handling, and API security.
4. **IPv6 Attack Surface Validation** — Use mitm6 to test whether IPv6 is enabled and exploitable in a predominantly IPv4 network, then chain with LDAP/SMB relay for domain escalation.
5. **Network Forensics and Incident Response** — Capture and analyze full PCAP to reconstruct communication timelines, extract transferred files, and identify data exfiltration.
6. **Traffic Manipulation and Injection** — Use bettercap caplets or mitmproxy scripts to inject JavaScript, modify responses, or replace downloaded files in transit.

---

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **wireshark/tshark** | Protocol analysis, PCAP triage, credential extraction, protocol hierarchy statistics | `tshark -r capture.pcap -Y "http.request"` |
| **tcpdump** | Lightweight packet capture with BPF filters, suitable for long-duration sniffing | `tcpdump -i eth0 -w capture.pcap` |
| **ettercap** | Classic ARP spoofing MITM tool with plugin system for SSL stripping and filtering | `ettercap -T -q -i eth0 -M arp:remote /target// /gateway//` |
| **bettercap** | Modular MITM framework with caplet scripting, ARP/DNS/DHCP spoofing, and credential sniffer | `bettercap -iface eth0` |
| **mitm6** | IPv6 MITM via SLAAC rogue router advertisement, chains to NTLM relay | `mitm6 -d domain.local -i eth0` |
| **responder** | LLMNR/NBT-NS/mDNS poisoner, captures NTLMv1/v2 hashes, HTTP/FTP/SMB auth | `responder -I eth0 -w -d -f` |
| **dsniff** | Suite of network sniffing tools: arpspoof, dnsspoof, urlsnarf, filesnarf, mailsnarf | `arpspoof -i eth0 -t victim gateway` |
| **driftnet** | Extracts images from HTTP traffic in real-time for visual reconnaissance | `driftnet -i eth0 -d /tmp/images` |
| **mitmproxy** | Interactive HTTPS proxy with Python scripting API for traffic analysis and modification | `mitmproxy -p 8080 --mode transparent` |

---

## Methodology

### Attack Chain

```
  Survey              Capture              Poison              Harvest
 (arp-scan)    →   (tcpdump/tshark)  →  (ettercap/bettercap)  →  (responder/dsniff)
                                                                    │
         Manipulate          Exfiltrate                            │
  (bettercap caplets) ←  (driftnet/filesnarf)  ←─────────────────┘
```

**Phase Details**:

1. **Survey** — Map the network topology using ARP scanning (`arp-scan -l`) and passive traffic observation. Identify the gateway IP, target hosts, VLAN structure, and any existing security controls (DAI, port security, 802.1X). Document MAC addresses and IP-to-host mappings for targeting.

2. **Capture** — Begin passive packet capture with tcpdump or tshark. Apply BPF/display filters to focus on target protocols. Identify cleartext services (HTTP, FTP, SMTP, IMAP, Telnet) and record credential patterns. This phase is completely undetectable on switched networks when using port mirroring or when operating on a hub/shared medium.

3. **Poison** — Establish MITM position through ARP spoofing (ettercap/bettercap), IPv6 SLAAC (mitm6), or DHCP spoofing. Select the poisoning technique based on the target environment: ARP spoof for Layer 2 adjacency, mitm6 for Windows domains with IPv6 enabled, or DNS spoof for targeted domain redirection.

4. **Harvest** — With MITM position established, run protocol-specific credential harvesters: Responder for LLMNR/NBT-NTLM hashes, dsniff for FTP/HTTP/Telnet credentials, bettercap sniffer module for API keys and cookies. Collect and categorize all harvested credentials.

5. **Manipulate** — Use bettercap caplets or mitmproxy scripts to modify traffic in transit: inject JavaScript into HTTP responses, replace file downloads, strip HTTPS to HTTP, or modify DNS responses. This phase demonstrates the impact of a MITM position beyond passive observation.

6. **Exfiltrate** — Extract images (driftnet), files (filesnarf), emails (mailsnarf), and URLs (urlsnarf) from intercepted traffic. Correlate captured data with host identities for reporting.

## Practical Steps

End-to-end sniffing / MITM engagement sequence. Each step references the relevant section above.

1. **Position** — Get into the path of the target traffic: ARP poison (LAN), rogue AP (Wi-Fi), or upstream tap (enterprise). See Methodology § Positioning.
2. **Capture** — Start `tcpdump` / `Wireshark` rolling before triggering the target traffic; rotate PCAP files at 100 MB to avoid loss.
3. **Decode** — Add `tcp.port==XXXX,http,tls,dns,smb,ftp` display filters; follow TCP streams to reconstruct sessions.
4. **Credential Mine** — Run `tshark -Y "ftp||http.request.method==POST||kerberos||ntlmssp" -T fields -e ...` over the PCAP; pipe to `hashcat` mode 5600 (NTLMv2) / 13100 (Kerberos).
5. **Downgrade & Strip** — For HTTPS targets: arpspoof + sslstrip + Bettercap `hstshijack/hsts-bypass`; verify downgrade success before pivoting.
6. **Modify** — Active MITM: inject Beef hooks, swap downloads, spoof DNS responses via `bettercap -X --proxy`.
7. **Persist** — Drop a passive backdoor (e.g., `pcapd` cron) for long-duration captures; rotate logs hourly.
8. **Cover** — Flush iptables NAT rules; restore ARP cache by sending gratuitous ARP from the spoofed gateway before exit.
9. **Report** — Convert PCAP to HTML via `tshark -G html`; redact unrelated traffic; map each finding to MITRE ATT&CK T1040/T1557.

For full automation scripts see `## Automation and Scripting`. For ethical / legal boundaries see `## Legal and Ethical Considerations`.

---

## Defense Evasion Techniques

Evade MITM detection during authorized testing by: targeting specific hosts rather than the entire subnet (reduces ARP noise), using bettercap's `set arp.spoof.internal false` to avoid poisoning inter-host traffic, employing selective DNS spoofing that only responds to specific domain queries, and using mitm6 instead of ARP spoofing in environments with IPv4-focused monitoring. For credential harvesting, run Responder with `--lm` to capture only LM hashes (less noisy) or in analysis mode (`-A`) first to identify opportunities before active poisoning.

---
