"""JSON HTTP transport for Ark APIs.

Windows 的系统代理默认只被 urllib 读取（curl 只读环境变量、不读注册表），代理节点
一抖就表现为 SSL: UNEXPECTED_EOF_WHILE_READING。pipeline 包已统一直连，见 __init__.py。
这里保留 Ark 走 curl 的路径，是不想依赖 Python 的 TLS 栈，与代理问题独立。
"""
import io
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request


ARK_HOST = "ark.cn-beijing.volces.com"


def _curl_config_header(value):
    """Escape a header for curl's stdin config; never put credentials in argv."""
    if "\r" in value or "\n" in value:
        raise ValueError("HTTP header contains a newline")
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _curl_json(req, timeout, curl_path):
    with tempfile.TemporaryDirectory(prefix="travelgen-ark-") as folder:
        response_path = os.path.join(folder, "response.json")
        args = [curl_path, "--silent", "--show-error", "--max-time", str(timeout),
                "--config", "-", "--output", response_path,
                "--write-out", "%{http_code}", "--request", req.get_method()]
        if req.data is not None:
            request_path = os.path.join(folder, "request.json")
            with open(request_path, "wb") as target:
                target.write(req.data)
            args += ["--data-binary", "@" + request_path]
        args.append(req.full_url)
        config = "".join(
            f'header = "{_curl_config_header(key)}: {_curl_config_header(value)}"\n'
            for key, value in req.header_items())
        try:
            result = subprocess.run(args, input=config.encode("utf-8"),
                                    capture_output=True, timeout=timeout + 5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise urllib.error.URLError(f"curl transport failed: {type(exc).__name__}") from None
        if result.returncode:
            raise urllib.error.URLError(f"curl transport failed (exit {result.returncode})")
        try:
            code = int(result.stdout.decode("ascii").strip())
            with open(response_path, "rb") as source:
                body = source.read()
        except (ValueError, OSError) as exc:
            raise urllib.error.URLError("curl transport returned an invalid response") from None
        if code >= 400:
            raise urllib.error.HTTPError(req.full_url, code, "HTTP error", {}, io.BytesIO(body))
        if code < 200 or code >= 300:
            raise urllib.error.URLError(f"unexpected HTTP status {code}")
        return json.loads(body.decode("utf-8"))


def request_json(req, timeout=60):
    host = urllib.parse.urlsplit(req.full_url).hostname
    if os.name == "nt" and host == ARK_HOST:
        curl_path = shutil.which("curl.exe")
        if curl_path:
            return _curl_json(req, timeout, curl_path)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def download_file(url, dest_path, timeout=120):
    """Download a provider video without leaving a partial file on failure."""
    folder = os.path.dirname(os.path.abspath(dest_path))
    os.makedirs(folder, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="travelgen-download-", dir=folder) as work:
        temp_path = os.path.join(work, "video.part")
        curl_path = shutil.which("curl.exe") if os.name == "nt" else None
        if curl_path:
            if "\r" in url or "\n" in url:
                raise ValueError("download URL contains a newline")
            config = f'url = "{_curl_config_header(url)}"\nheader = "User-Agent: Mozilla/5.0"\n'
            args = [curl_path, "--silent", "--show-error", "--location", "--max-redirs", "5",
                    "--max-time", str(timeout), "--config", "-", "--output", temp_path,
                    "--write-out", "%{http_code}"]
            try:
                result = subprocess.run(args, input=config.encode("utf-8"),
                                        capture_output=True, timeout=timeout + 5)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise urllib.error.URLError(f"curl download failed: {type(exc).__name__}") from None
            if result.returncode:
                raise urllib.error.URLError(f"curl download failed (exit {result.returncode})")
            try:
                code = int(result.stdout.decode("ascii").strip())
            except ValueError:
                raise urllib.error.URLError("curl download returned an invalid status") from None
            if code < 200 or code >= 300:
                raise urllib.error.HTTPError(url, code, "download failed", {}, None)
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as response, open(temp_path, "wb") as target:
                shutil.copyfileobj(response, target)
        size = os.path.getsize(temp_path)
        if size == 0:
            raise urllib.error.URLError("download returned an empty file")
        os.replace(temp_path, dest_path)
        return size
