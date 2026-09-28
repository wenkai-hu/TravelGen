# -*- coding: utf-8 -*-
"""火山方舟 Seedance 2.0 Pro 视频生成客户端（Phase 3 实测规范：results/03_video 样片）。

- 提交：POST /contents/generations/tasks（Bearer 鉴权，异步任务）
- 轮询：GET /contents/generations/tasks/{id}，状态机 queued→running→succeeded/failed/expired
- ⚠️ video_url 仅 24h 有效，成功即下载转存 assets/videos/（不入库，见 .gitignore）
- 成本：约 1 元/条（5s 1080p）
"""
import json, os, subprocess, urllib.request, urllib.error

CONTENT_TYPES = {"video_url": "succeeded", "url": "succeeded"}


class NetworkError(Exception):
    """网络层异常（SSL EOF／超时／连接重置）。与业务失败区分：同一个请求稍后重试即可。"""


def _request(req, timeout=60):
    """统一发请求：HTTP 错误转 error dict（业务失败），网络层异常抛 NetworkError（可重试）。
    ⚠️ HTTPError 是 URLError 的子类，必须先 catch。"""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": {"code": e.code, "message": e.read().decode("utf-8", "ignore")[:300]}}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise NetworkError(f"{type(exc).__name__}: {exc}") from exc


def _post(provider, path, body):
    url = provider["base_url"].rstrip("/") + path
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {provider['api_key']}"}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
    return _request(req)


def _get(provider, path):
    url = provider["base_url"].rstrip("/") + path
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {provider['api_key']}"})
    return _request(req)


def submit(provider, prompt, duration=5, resolution="1080p", ratio="adaptive", images=None,
           audio=None, generate_audio=False, video=None):
    """提交单镜头生成任务；返回 (task_id, error)。task_id 形如 cpt-xxx。
    ratio 对应请求里的 aspect_ratio（官方字段名 ratio，9:16 竖屏短视频必须显式传，
    否则默认 adaptive 自适应比例）。
    images: 可选的参考图 URL/data-URI 列表（Seedance 2.0 多模态参考，role=reference_image，
    顺序即提示词中"图片1/图片2"的编号）；None 时纯文本，与原行为一致。"""
    content = [{"type": "text", "text": prompt}]
    if images:
        content += [{"type": "image_url", "image_url": {"url": u}, "role": "reference_image"}
                    for u in images[:9]]  # 官方上限 9 张
    if video:
        content.append({"type": "video_url", "video_url": {"url": video},
                        "role": "reference_video"})
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


def submit_safe(provider, *args, **kwargs):
    """submit 的网络异常版：连接类错误不冒泡，按 (None, 错误文本) 返回，交给上层按失败重试。
    批次里一条片段网络抖动不应该让整批生成失败（见 pipeline._run_*_jobs）。"""
    try:
        return submit(provider, *args, **kwargs)
    except NetworkError as exc:
        return None, f"网络错误（{exc}）"


def get_task_safe(provider, task_id):
    """get_task 的网络异常版：连接类错误按"仍在进行"返回，让轮询继续（由轮询上限兜底）。"""
    try:
        return get_task(provider, task_id)
    except NetworkError as exc:
        return "running", None, f"网络错误（{exc}）"


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


def normalize_av(src, dest, duration):
    """保留 Seedance 原生旁白/环境声，统一为可拼接的 H.264 + AAC 音视频。"""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
    except ImportError:
        return False
    tmp = dest + ".tmp.mp4"
    video_filter = f"fps=30,setsar=1,tpad=stop_mode=clone:stop_duration=1,trim=duration={duration},setpts=PTS-STARTPTS"
    audio_filter = f"aresample=48000,apad=pad_dur=1,atrim=duration={duration},asetpts=PTS-STARTPTS"
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
           "-filter_complex", f"[0:v]{video_filter}[v];[0:a]{audio_filter}[a]",
           "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", tmp]
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


def extract_audio(src, dest):
    """提取 Seedance 原生音轨供试听与 QA，统一为 32kHz 双声道 PCM16。"""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
    except ImportError:
        return False
    tmp = dest + ".tmp.wav"
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-vn",
           "-ac", "2", "-ar", "32000", "-c:a", "pcm_s16le", tmp]
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


def create_placeholder_av(dest, duration, resolution="720p", ratio="9:16"):
    """demo 模式生成带静音音轨的真实占位 Segment，走与正式成片相同的 AV 拼接。"""
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
           "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration}",
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", dest]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=300).returncode == 0
    except Exception:
        return False
