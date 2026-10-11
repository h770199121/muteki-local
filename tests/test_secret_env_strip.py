"""Host-run unittest: secret env values must not carry trailing whitespace.

Regression for the opencode JSONC break: a .env-sourced API_KEY with a
trailing newline was passed through unstripped, and opencode's {env:VAR}
pre-parse spliced the newline into its JSONC ("UnexpectedEndOfString").
The file-read branch already stripped; only the env-source branch leaked.

Stdlib-only so it runs on the host (no pytest/pydantic required).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from muteki.solver.credential_accounts import _add_secret_file_or_env

# dummy values assembled at runtime — never a real credential
_KEY_CLEAN = "-".join(["unit", "test", "key", "01"])
_KEY_DIRTY = _KEY_CLEAN + "\n"
_KEY_CRLF = _KEY_CLEAN + "\r\n"


class SecretEnvStripTests(unittest.TestCase):
    def _call(self, out, *, base=None, filename="API_KEY", env_name="API_KEY",
              container=False, container_path="", source=None):
        _add_secret_file_or_env(
            out,
            base=base,
            filename=filename,
            env_name=env_name,
            container=container,
            container_path=container_path,
            source=source or {},
        )

    def test_env_value_with_trailing_newline_is_stripped(self):
        out = {}
        self._call(out, source={"API_KEY": _KEY_DIRTY})
        self.assertEqual(out.get("API_KEY"), _KEY_CLEAN)

    def test_env_value_with_crlf_is_stripped(self):
        out = {}
        self._call(out, source={"API_KEY": _KEY_CRLF})
        self.assertEqual(out.get("API_KEY"), _KEY_CLEAN)

    def test_env_value_whitespace_only_is_omitted(self):
        out = {}
        self._call(out, source={"API_KEY": "\n"})
        self.assertNotIn("API_KEY", out)

    def test_clean_env_value_passes_through(self):
        out = {}
        self._call(out, source={"API_KEY": _KEY_CLEAN})
        self.assertEqual(out.get("API_KEY"), _KEY_CLEAN)

    def test_file_branch_still_strips(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "API_KEY").write_text(_KEY_DIRTY, encoding="utf-8")
            out = {}
            self._call(out, base=base)
            self.assertEqual(out.get("API_KEY"), _KEY_CLEAN)

    def test_container_branch_uses_file_pointer_not_value(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "API_KEY").write_text(_KEY_DIRTY, encoding="utf-8")
            out = {}
            self._call(out, base=base, container=True,
                       container_path="/run/muteki/accounts/a/API_KEY")
            self.assertEqual(out.get("API_KEY_FILE"),
                             "/run/muteki/accounts/a/API_KEY")
            self.assertNotIn("API_KEY", out)


if __name__ == "__main__":
    unittest.main()
