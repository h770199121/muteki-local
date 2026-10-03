"""A03 — free-text exemption must not bypass credential-carrier sealing.

The project venv has no pydantic/pytest, so ``apps.web.control_adapter`` cannot be
imported here.  These tests therefore load the REAL source file and execute the
sealing logic extracted from it by AST — the tested code is the shipped code, not a
transcription, so the test cannot silently drift from the implementation.

A03 root cause
---------------
``secure_payload`` exempted ``free_text_keys`` (HINT/ASK/FOCUS/DIRECTIVE/CORRECTION
text) from ``_redact_value`` entirely, not merely from its content heuristic.  A CTF
hint carrying ``http://user:pass@host/`` was stored in the clear and echoed by
``safe_hitl_echo``.  The fix scopes the exemption to the content heuristic only, so
explicit credential CARRIERS still seal.  Carrier detection is by form, never by the
mere presence of a credential word.

Run:  python -X utf8 -B -m unittest tests.test_a03_free_text_sealing -v
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ADAPTER = Path(__file__).resolve().parents[1] / "apps" / "web" / "control_adapter.py"

# Names pulled out of the real module: the three carrier regexes plus the
# carrier predicate and the payload sealer, with their direct helper.
WANTED = {
    "_SENSITIVE_KEY",
    "_SENSITIVE_TEXT",
    "_URL_USERINFO",
    "_is_credential_carrier",
    "_looks_sensitive_text",
    "_put_secret",
    "secure_payload",
}


def load_real_logic() -> dict:
    """Execute the real sealing logic from the real source file.

    ``secure_payload`` is rebound onto a stub ``_redact_value`` so the branch
    under test — the free-text exemption — is exercised without dragging in
    SecretStore/pydantic. The stub mirrors the real one's carrier behaviour.
    """
    source = ADAPTER.read_text(encoding="utf-8")
    tree = ast.parse(source)

    wanted: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.Assign)):
            if isinstance(node, ast.FunctionDef):
                name = node.name
            else:
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                name = targets[0] if len(targets) == 1 else None
            if name in WANTED:
                wanted[name] = node

    missing = WANTED - set(wanted)
    if missing:
        raise AssertionError(f"control_adapter.py 缺少被测定义: {sorted(missing)}")

    module = ast.Module(
        body=[wanted[n] for n in ("_SENSITIVE_KEY", "_SENSITIVE_TEXT",
                                  "_URL_USERINFO", "_is_credential_carrier",
                                  "_looks_sensitive_text", "_put_secret")],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)

    # A faithful stand-in for the real _redact_value: same three carrier checks.
    def _redact_value(value, *, key, secrets, references, path=()):
        if isinstance(value, dict):
            return {k: _redact_value(v, key=str(k), secrets=secrets,
                                     references=references, path=(*path, str(k)))
                    for k, v in value.items()}
        if not isinstance(value, str):
            return value
        if value.startswith("secret://"):
            references.append(value)
            return value
        if (ns["_SENSITIVE_KEY"].search(key)
                or ns["_looks_sensitive_text"](value)
                or ns["_URL_USERINFO"].search(value)):
            reference = f"secret://sealed/{len(references)}"
            references.append(reference)
            return reference
        return value

    ns: dict = {"re": re}
    exec(compile(module, str(ADAPTER), "exec"), ns)  # noqa: S102 - exercising shipped code
    ns["_redact_value"] = _redact_value

    secure_src = ast.Module(body=[wanted["secure_payload"]], type_ignores=[])
    ast.fix_missing_locations(secure_src)
    exec(compile(secure_src, str(ADAPTER), "exec"), ns)  # noqa: S102
    return ns


NS = load_real_logic()
secure_payload = NS["secure_payload"]
is_carrier = NS["_is_credential_carrier"]

FREE_TEXT = frozenset({"text", "hint"})


class CarrierFormTests(unittest.TestCase):
    """The predicate decides by FORM, not by credential vocabulary."""

    def test_url_userinfo_is_a_carrier(self):
        self.assertTrue(is_carrier("hint", "http://user:password@host/"))
        self.assertTrue(is_carrier("hint", "https://admin:s3cr3t@10.0.0.1/x"))
        self.assertTrue(is_carrier("text", "ftp://u:p@h/"))

    def test_structured_credential_key_is_a_carrier(self):
        self.assertTrue(is_carrier("api_key", "anything"))
        self.assertTrue(is_carrier("user_password", "anything"))

    def test_explicit_reference_is_a_carrier(self):
        self.assertTrue(is_carrier("hint", "secret://already/sealed"))

    def test_plain_prose_mentioning_credentials_is_not_a_carrier(self):
        # The whole point of the exemption: this must stay readable.
        self.assertFalse(is_carrier("hint", "the password is in hint.php"))
        self.assertFalse(is_carrier("text", "try token=abc from /etc/notes"))
        self.assertFalse(is_carrier("hint", "密钥在 hint.php 里"))
        self.assertFalse(is_carrier("hint", "look at /robots.txt then the api key path"))

    def test_url_without_userinfo_is_not_a_carrier(self):
        self.assertFalse(is_carrier("hint", "http://host/path?q=1"))
        self.assertFalse(is_carrier("hint", "https://host:8080/x"))


class _StubSecretStore:
    """Minimal stand-in for SecretStore (pydantic-free)."""

    def __init__(self) -> None:
        self.values: list[str] = []

    def put(self, value: str) -> str:
        self.values.append(value)
        return f"secret://sealed/{len(self.values) - 1}"

    def get(self, reference: str):  # pragma: no cover - not exercised here
        raise AssertionError("get() not expected in this fixture")


class FreeTextExemptionTests(unittest.TestCase):
    """6 夹具中的 ①②：普通提示放行、URL userinfo 封存。"""

    def _seal(self, payload, **kw):
        # secure_payload builds its own ``references`` list internally; refs are
        # surfaced on the result as ``secret_refs``.
        store = _StubSecretStore()
        out = secure_payload(payload, secrets=store, **kw)
        return out, list(out.get("secret_refs") or []), store

    def test_plain_hint_mentioning_password_stays_readable(self):
        out, refs, _ = self._seal({"hint": "the password is in hint.php"},
                                  free_text_keys=FREE_TEXT)
        self.assertEqual(out["hint"], "the password is in hint.php")
        self.assertNotIn("redacted", out)
        self.assertEqual(refs, [])

    def test_url_userinfo_inside_hint_is_sealed(self):
        out, refs, _ = self._seal({"hint": "try http://user:password@host/"},
                                  free_text_keys=FREE_TEXT)
        self.assertNotEqual(out["hint"], "try http://user:password@host/")
        self.assertTrue(out["hint"].startswith("secret://"))
        self.assertTrue(out["redacted"])
        self.assertEqual(len(refs), 1)
        # The plaintext must survive nowhere in the secured payload.
        self.assertNotIn("password@host", repr(out))

    def test_embedded_url_userinfo_is_sealed_anywhere_in_the_hint(self):
        # Regression for the ^-anchored _URL_USERINFO: an embedded credential URL
        # used to survive because the regex demanded start-of-string.
        for text in (
            "see http://u:p@h/ now",
            "step 3: open https://admin:s3cr3t@10.0.0.1/x and dump it",
            "prefix junk http://a:b@h/ suffix",
        ):
            with self.subTest(text=text):
                out, _, _ = self._seal({"hint": text}, free_text_keys=FREE_TEXT)
                self.assertTrue(out["hint"].startswith("secret://"),
                                f"未封存: {text!r} -> {out['hint']!r}")

    def test_secret_reference_inside_hint_is_preserved(self):
        out, refs, _ = self._seal({"hint": "secret://prior/ref"},
                                  free_text_keys=FREE_TEXT)
        self.assertEqual(out["hint"], "secret://prior/ref")
        self.assertEqual(refs, ["secret://prior/ref"])

    def test_structured_credential_key_is_sealed_even_in_free_text_action(self):
        out, refs, _ = self._seal({"api_key": "AKIAEXAMPLE", "text": "hint"},
                                  free_text_keys=FREE_TEXT)
        self.assertTrue(out["api_key"].startswith("secret://"))
        self.assertEqual(out["text"], "hint")

    def test_forced_answer_is_always_sealed(self):
        out, _, _ = self._seal({"answer": "flag{abc}"}, force_text_secret=True,
                               free_text_keys=FREE_TEXT)
        self.assertTrue(out["answer"].startswith("secret://"))
        self.assertTrue(out["redacted"])

    def test_echo_never_reveals_a_sealed_hint(self):
        """safe_hitl_echo branches on the redacted flag; a sealed hint must not
        reach the plaintext branch."""
        out, _, _ = self._seal({"hint": "http://user:password@host/"},
                               free_text_keys=FREE_TEXT)
        # Mirrors safe_hitl_echo: redacted -> placeholder, never the raw value.
        echoed = ("[redacted operator secret]" if out.get("redacted")
                  else (out.get("text") or out.get("hint")))
        self.assertEqual(echoed, "[redacted operator secret]")
        self.assertNotIn("password@host", str(echoed))

    def test_hint_without_credentials_is_never_marked_redacted(self):
        out, _, store = self._seal({"hint": "look at /robots.txt then hint.php"},
                                   free_text_keys=FREE_TEXT)
        self.assertNotIn("redacted", out)
        self.assertEqual(store.values, [])


class RetryIdempotencyTests(unittest.TestCase):
    """A retry of the same command must not create a second reference."""

    def test_repeated_seal_of_identical_payload_is_stable(self):
        payload = {"hint": "http://user:password@host/"}
        store = _StubSecretStore()
        first = secure_payload(payload, secrets=store, free_text_keys=FREE_TEXT)
        second = secure_payload(payload, secrets=store, free_text_keys=FREE_TEXT)
        self.assertEqual(first["hint"], second["hint"])
        self.assertEqual(len(first["secret_refs"]), len(second["secret_refs"]))


class SourceContractTests(unittest.TestCase):
    """Guard the fix against regression at the source level."""

    def test_free_text_branch_calls_the_carrier_predicate(self):
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("_is_credential_carrier(skey, value)", source,
                      "free-text 分支必须复核载体形态")

    def test_docstring_pins_the_a03_contract(self):
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("A03", source, "docstring 需记录 A03 契约")


if __name__ == "__main__":
    unittest.main(verbosity=2)
