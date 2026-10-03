# Operator insights (hindsight capture)

Human-captured lessons from watching runs on the Command Deck. One note = one fact + one working command/payload. Indexed by kbsearch.py; projected into every worker automatically.

---


## N-20260929-1 [nopass,filter-bypass] web-sqli
_2026-09-29 20:31_

no-pass-needed (CSAW21Q): server replaces 'admin' once in username before SQL query; trim_whitespace truncates at first space. Working bypass: username=adadminmin'-- (nest keyword k[:2]+k+k[2:] so filter restores admin'--). NEVER parse the cookie jar by hand — use curl -c jar then curl -b jar (grep 'connect.sid=' on a Netscape jar always returns empty).

---

## N-20260930-1 [include,lfi,php,base64-pollution] file-inclusion
_2026-09-30 13:23_

PHP LFI filter-chain STANDARD (3 steps): (1) probe ?file=param with a known file first (?file=flag.php often echoes a hint); (2) read SOURCE via curl -s "URL/?file=php://filter/convert.base64-encode/resource=flag.php" (or php://filter/read=convert.base64-encode/...); (3) CRITICAL: the response usually has an HTML prefix (e.g. <meta charset="utf8">) that breaks base64 -d SILENTLY (exit != 0, stderr swallowed). NEVER pipe raw output into base64 -d. Strip non-base64 lines first: curl -s URL | grep -oE '[A-Za-z0-9+/=]{16,}' | base64 -d 2>/dev/null | head -20. The flag may be in a PHP COMMENT (//CTF2{...}) — read the WHOLE decoded output, do not grep for flag{ only: flag prefixes vary (CTF2{, csawctf{, FLAG{...}). If base64 -d output is empty, you skipped step 3 — re-run with the grep strip.

---

## N-20261003-1 [include,checkfile,traversal] file-inclusion
_2026-10-03 12:49_

DASCTF Include 2026-10-03 instance (checkFile whitelist variant): direction was right (read source.php, read hint.php, build hint.php?xxx bypass) but traversal depth never exceeded 1 while the flag needed 5. Rule: when an include param passes a whitelist check but the file is not found, enumerate traversal depth 1-8 in one for-loop with tail -c 120 calibration — never repeat one depth. Full card: kb/file-inclusion.md 'Whitelist checkFile Pattern'.

---
