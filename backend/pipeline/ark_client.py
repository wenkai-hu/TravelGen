# -*- coding: utf-8 -*-
"""火山方舟 Seedance 2.0 Pro 视频生成客户端（Phase 3 实测规范：results/03_video 样片）。

- 提交：POST /contents/generations/tasks（Bearer 鉴权，异步任务）
- 轮询：GET /contents/generations/tasks/{id}，状态机 queued→running→succeeded/failed/expired
- ⚠️ video_url 仅 24h 有效，成功即下载转存 assets/videos/（不入库，见 .gitignore）
- 成本：约 1 元/条（5s 1080p）
"""
import json, os, subprocess, urllib.request, urllib.error

CONTENT_TYPES = {"video_url": "succeeded", "url": "succeeded"}


def _post(provider, path, body):
    url = provider["base_url"].rstrip("/") + path
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {provider['api_key']}"}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": {"code": e.code, "message": e.read().decode("utf-8", "ignore")[:300]}}


def _get(provider, path):
    url = provider["base_url"].rstrip("/") + path
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {provider['api_key']}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": {"code": e.code, "message": e.read().decode("utf-8", "ignore")[:300]}}


def submit(provider, prompt, duration=5, resolution="1080p", ratio="adaptive", images=None,
           audio=None, generate_audio=False):
    """提交单镜头生成任务；返回 (task_id, error)。task_id 形如 cpt-xxx。
    ratio 对应请求里的 aspect_ratio（官方字段名 ratio，9:16 竖屏短视频必须显式传，
    否则默认 adaptive 自适应比例）。
    images: 可选的参考图 URL/data-URI 列表（Seedance 2.0 多模态参考，role=reference_image，
    顺序即提示词中"图片1/图片2"的编号）；None 时纯文本，与原行为一致。"""
    content = [{"type": "text", "text": prompt}]
    if images:
        content += [{"type": "image_url", "image_url": {"url": u}, "role": "reference_image"}
                    for u in images[:9]]  # 官方上限 9 张
    if audio:
        content.append({"type": "audio_url", "audio_url": {"url": audio},
                        "role": "reference_audio"})
    body = {"model": provider["model"],
            "content": content,
            "duration": duration,
            "resolution": resolution,
            "ratio": ratio}
    if generate_audio:
        body["generate_audio"] = True
    data = _post(provider, "/contents/generations/tasks", body)
    if data.get("error"):
        return None, f"提交失败({data['error'].get('code')}): {data['error'].get('message', '')}"
    tid = data.get("id")
    if not tid:
        return None, f"响应无任务ID: {str(data)[:200]}"
    return tid, None


def get_task(provider, task_id):
    """查询任务；返回 (status, video_url, error)。"""
    data = _get(provider, f"/contents/generations/tasks/{task_id}")
    if data.get("error"):
        return "failed", None, f"查询失败({data['error'].get('code')}): {data['error'].get('message', '')}"
    status = data.get("status", "unknown")
    url = None
    if status == "succeeded":
        content = data.get("content") or {}
        url = content.get("video_url") or content.get("url")
        if not url:
            return "failed", None, f"succeeded 但无视频URL: {str(data)[:200]}"
    return status, url, None


def download(url, dest_path):
    """下载视频到本地；返回文件字节数。"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(dest_path, "wb") as f:
            f.write(resp.read())
    return os.path.getsize(dest_path)


def transcode_web(src, dest):
    """Seedance 输出 H.264（非 faststart）+ 自动附 BGM 音轨 → 转码成浏览器可播格式（yuv420p + faststart）。

    同时 -an 去除音轨：Seedance 每镜自动配的 BGM 各不相同，拼接前统一配乐，否则后期剪辑音轨打架。
    返回是否成功。失败时调用方保留原始文件（下载兜底仍可用）。imageio-ffmpeg 未装则直接返回 False。
    """
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
    except ImportError:
        return False
    tmp = dest + ".tmp.mp4"
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            return False
        os.replace(tmp, dest)
        return True
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False


def normalize_visual_only(src, dest):
    """保留 Seedance 原始文件，另存浏览器可播的无声画面轨。"""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
    except ImportError:
        return False
    tmp = dest + ".tmp.mp4"
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            return False
        os.replace(tmp, dest)
        return True
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False


def mux_audio(visual_path, audio_path, dest):
    """把原始 master audio 切片回铺到单个 Segment 预览。"""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
    except ImportError:
        return False
    tmp = dest + ".tmp.mp4"
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y",
           "-i", visual_path, "-i", audio_path,
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", tmp]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            return False
        os.replace(tmp, dest)
        return True
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False


def create_placeholder_video(dest, duration, resolution="720p", ratio="9:16"):
    """demo 模式生成真实可拼接的静音占位视频。"""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
    except ImportError:
        return False
    short = 1080 if resolution == "1080p" else 720
    if ratio == "16:9":
        width, height = round(short * 16 / 9 / 2) * 2, short
    elif ratio == "1:1":
        width = height = short
    else:
        width, height = short, round(short * 16 / 9 / 2) * 2
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"color=c=0x173b3f:s={width}x{height}:r=30:d={duration}",
           "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", dest]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=300).returncode == 0
    except Exception:
        return False
