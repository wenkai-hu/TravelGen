"""Run: .venv/Scripts/python -m unittest discover -s backend -p test_http_transport.py"""
import json
import io
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from pipeline import http_transport


class ArkTransportTests(unittest.TestCase):
    def setUp(self):
        self.req = urllib.request.Request(
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            data=b'{"model":"test"}',
            headers={"Authorization": "Bearer test-secret", "Content-Type": "application/json"})

    def test_curl_keeps_secret_out_of_process_arguments_and_returns_json(self):
        def fake_run(args, *, input, capture_output, timeout):
            self.assertNotIn("test-secret", " ".join(args))
            self.assertIn(b"test-secret", input)
            self.assertEqual(Path(args[args.index("--data-binary") + 1][1:]).read_bytes(),
                             self.req.data)
            Path(args[args.index("--output") + 1]).write_text('{"ok":true}')
            return type("Result", (), {"returncode": 0, "stdout": b"200"})()

        with patch.object(http_transport.subprocess, "run", side_effect=fake_run):
            self.assertEqual(http_transport._curl_json(self.req, 10, "curl.exe"), {"ok": True})

    def test_http_error_preserves_status_and_body_for_caller(self):
        def fake_run(args, **kwargs):
            Path(args[args.index("--output") + 1]).write_text('{"error":"invalid"}')
            return type("Result", (), {"returncode": 0, "stdout": b"401"})()

        with patch.object(http_transport.subprocess, "run", side_effect=fake_run), \
                self.assertRaises(urllib.error.HTTPError) as raised:
            http_transport._curl_json(self.req, 10, "curl.exe")
        self.assertEqual(raised.exception.code, 401)
        self.assertEqual(json.loads(raised.exception.read()), {"error": "invalid"})

    def test_network_failure_has_no_credentials(self):
        with patch.object(http_transport.subprocess, "run", return_value=type(
                "Result", (), {"returncode": 35, "stdout": b"000"})()), \
                self.assertRaises(urllib.error.URLError) as raised:
            http_transport._curl_json(self.req, 10, "curl.exe")
        self.assertNotIn("test-secret", str(raised.exception))
        self.assertIn("exit 35", str(raised.exception))

    def test_windows_ark_uses_curl_transport(self):
        with patch.object(http_transport.os, "name", "nt"), \
                patch.object(http_transport.shutil, "which", return_value="curl.exe"), \
                patch.object(http_transport, "_curl_json", return_value={"ok": True}) as curl:
            self.assertEqual(http_transport.request_json(self.req), {"ok": True})
        self.assertIs(curl.call_args.args[0], self.req)

    def test_non_windows_uses_standard_library_without_curl(self):
        with patch.object(http_transport.os, "name", "posix"), \
                patch.object(http_transport.shutil, "which") as which, \
                patch.object(http_transport.urllib.request, "urlopen",
                             return_value=io.BytesIO(b'{"ok":true}')) as open_url:
            self.assertEqual(http_transport.request_json(self.req, timeout=12), {"ok": True})
        which.assert_not_called()
        self.assertEqual(open_url.call_args.kwargs["timeout"], 12)

    def test_windows_without_curl_uses_standard_library(self):
        with patch.object(http_transport.os, "name", "nt"), \
                patch.object(http_transport.shutil, "which", return_value=None), \
                patch.object(http_transport.urllib.request, "urlopen",
                             return_value=io.BytesIO(b'{"ok":true}')) as open_url:
            self.assertEqual(http_transport.request_json(self.req), {"ok": True})
        open_url.assert_called_once()

    def test_windows_other_host_uses_standard_library(self):
        req = urllib.request.Request("https://example.com/api")
        with patch.object(http_transport.os, "name", "nt"), \
                patch.object(http_transport.shutil, "which") as which, \
                patch.object(http_transport.urllib.request, "urlopen",
                             return_value=io.BytesIO(b'{"ok":true}')) as open_url:
            self.assertEqual(http_transport.request_json(req), {"ok": True})
        which.assert_not_called()
        open_url.assert_called_once()

    def test_windows_download_uses_curl_for_signed_video_url(self):
        signed_url = "https://video.example.com/file.mp4?token=test-secret"
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "voice.mp4"

            def fake_run(args, *, input, capture_output, timeout):
                self.assertNotIn("test-secret", " ".join(args))
                self.assertIn(b"test-secret", input)
                self.assertIn("--location", args)
                Path(args[args.index("--output") + 1]).write_bytes(b"video bytes")
                return type("Result", (), {"returncode": 0, "stdout": b"200"})()

            with patch.object(http_transport.os, "name", "nt"), \
                    patch.object(http_transport.shutil, "which", return_value="curl.exe"), \
                    patch.object(http_transport.subprocess, "run", side_effect=fake_run):
                size = http_transport.download_file(signed_url, dest)
            self.assertEqual(size, len(b"video bytes"))
            self.assertEqual(dest.read_bytes(), b"video bytes")

    def test_failed_download_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "voice.mp4"
            dest.write_bytes(b"previous")
            with patch.object(http_transport.os, "name", "nt"), \
                    patch.object(http_transport.shutil, "which", return_value="curl.exe"), \
                    patch.object(http_transport.subprocess, "run", return_value=type(
                        "Result", (), {"returncode": 35, "stdout": b"000"})()), \
                    self.assertRaises(urllib.error.URLError):
                http_transport.download_file("https://video.example.com/file.mp4", dest)
            self.assertEqual(dest.read_bytes(), b"previous")
