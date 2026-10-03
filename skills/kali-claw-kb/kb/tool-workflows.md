# Offline CTF tool workflows / 离线工具操作

These are local Muteki execution helpers, not additional attack recipes. All use
the standard library. Replace example paths/URLs with the actual challenge input.

## Tool entrypoints / 工具路径

```bash
python3 .agents/skills/kali-claw-kb/ctf_tools.py doctor
```

Use the returned absolute path. The current Kali image may expose Ghidra as
`/usr/share/ghidra/support/analyzeHeadless` and Volatility as `vol` rather than
`vol3`. Discovery distinguishes missing tools from startup/operation failures.
No package is installed by this command. In an offline run, report unavailable
dependencies instead of trying online installers.

## HTTP session cookie jar redirect / 会话保持与跳转

One session directory owns one cookie jar and an append-only set of response
artifacts. Reuse the same directory after a login or any state-changing request.
Do not manually parse Netscape cookie-jar text.

```bash
python3 .agents/skills/kali-claw-kb/ctf_tools.py http \
  http://LOCAL_CHALLENGE/login --session shared/http-session \
  --form 'username=PLAYER_INPUT' --form 'password=PLAYER_INPUT'
python3 .agents/skills/kali-claw-kb/ctf_tools.py http \
  http://LOCAL_CHALLENGE/home --session shared/http-session
```

The helper URL-encodes form fields, follows redirects, saves session cookies
across CLI processes, and returns status, redirect history, body_file,
metadata_file, SHA-256 and a preview. Raw response bytes remain in body_file.
Response size limits are explicit; `truncated: true` means incomplete evidence.
`--proxy` is explicit; environment proxies are not used. TLS verification stays
enabled. A 403/500 is a preserved target observation; connection failure is a
structured tool error with exit code 2.

## Input echo filter comparison / 输入回显与过滤对比

Use `--echo-field username` on a form request to retain submitted and echoed
input values. Use `--compare PATH_TO_PREVIOUS_METADATA.json` to compare status,
body hash and size and save the full textual diff. This is observation only:
it does not prove a vulnerability or choose a payload for you.

## Base64 decode HTML wrapper / 包装内容解码

```bash
python3 .agents/skills/kali-claw-kb/ctf_tools.py decode \
  shared/http-session/RESPONSE.body --format base64 --out-dir shared/decoded
```

The helper examines text nodes when HTML wrappers are present, supports URL-safe
unpadded base64, retains decoded bytes, and reports each candidate's type/hash.
For hex use `--format hex`; `--format auto` tries both. Multiple candidates are
possible. Inspect their saved files and verify expected structure; successful
decoding alone is not proof that a candidate is relevant to the challenge.

Preserve the original response. Do not hide decoder stderr or discard responses
because a hand-written pipe failed. Flag formats come from the challenge, not a
hard-coded `flag{` filter. Any recovered result still needs the normal Muteki
Blackboard submission and execution-source validation.
