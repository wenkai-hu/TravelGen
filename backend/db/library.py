"""Small synchronous repository for the existing synchronous pipeline save hooks.

The async login API and this repository share the same MySQL database. Each write
uses a short transaction; files stay under assets/, not inside database rows.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from .database import _db_url
from .models import AssetRecord, ProjectRecord, TaskRecord, User, VoiceRecord, utcnow

REPO = Path(__file__).resolve().parents[2]
ASSET_ROOT = REPO / "assets"
log = logging.getLogger(__name__)


def timestamp(value):
    if not value:
        return utcnow()
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


class Library:
    def __init__(self, engine=None, asset_root=None):
        url = make_url(_db_url()).set(drivername="mysql+pymysql") if engine is None else None
        self.engine = engine if engine is not None else create_engine(url, pool_pre_ping=True)
        self.asset_root = Path(asset_root or ASSET_ROOT).resolve()

    def save_project(self, data, *, importing=False):
        with Session(self.engine) as db, db.begin():
            user_id = db.scalar(select(User.id).where(User.username == data.get("username", "")))
            if user_id is None:
                if importing:
                    return False
                raise ValueError("项目所属用户不存在")
            row = db.get(ProjectRecord, data["project_id"])
            if row and importing:
                return False
            if row is None:
                row = ProjectRecord(id=data["project_id"], user_id=user_id,
                                    created_at=timestamp(data.get("created_at")))
                db.add(row)
            row.name = data.get("name") or data.get("request", {}).get("theme") or "未命名项目"
            row.status = data["status"]
            row.draft = data.get("draft", {})
            row.data = data
            row.updated_at = timestamp(data.get("updated_at"))
            row.deleted_at = timestamp(data["deleted_at"]) if data.get("deleted_at") else None
            return True

    def get_project(self, pid):
        with Session(self.engine) as db:
            row = db.get(ProjectRecord, pid)
            return dict(row.data) if row and not row.deleted_at else None

    def projects(self, username=None):
        with Session(self.engine) as db:
            query = select(ProjectRecord).where(ProjectRecord.deleted_at.is_(None))
            if username is not None:
                query = query.join(User).where(User.username == username)
            return [dict(row.data) for row in db.scalars(query.order_by(ProjectRecord.updated_at.desc()))]

    def get_task(self, tid, kind=None):
        with Session(self.engine) as db:
            row = db.get(TaskRecord, tid)
            return dict(row.data) if row and (kind is None or row.kind == kind) else None

    def save_task(self, data, kind, *, importing=False):
        with Session(self.engine) as db, db.begin():
            project = db.get(ProjectRecord, data["project_id"])
            if not project:
                if importing:
                    return False
                raise ValueError("请先保存任务所属项目")
            row = db.get(TaskRecord, data["task_id"])
            if row and importing:
                return False
            if row is None:
                row = TaskRecord(id=data["task_id"], project_id=project.id, kind=kind,
                                 created_at=timestamp(data.get("created_at")))
                db.add(row)
            row.status, row.data = data["status"], data
            row.updated_at = timestamp(data.get("updated_at"))
            db.flush()
            self._archive_outputs(db, project, row)
            return True

    def _key(self, path=None, url=None):
        if path:
            candidate = Path(path).resolve()
        elif url and url.startswith("/assets/"):
            candidate = (self.asset_root / unquote(url[len("/assets/"):])).resolve()
        else:
            return None  # Remote provider links are not durable library files.
        try:
            return candidate.relative_to(self.asset_root).as_posix()
        except ValueError:
            return None

    def _asset(self, db, project, task, kind, output_key, name, path=None, url=None, metadata=None):
        key = self._key(path, url)
        if not key:
            return None
        asset_id = "a_" + hashlib.sha256(f"{task.id}:{output_key}".encode()).hexdigest()[:40]
        asset = db.get(AssetRecord, asset_id)
        if asset:
            return asset  # Immutable output and soft deletion survive later progress saves.
        asset = AssetRecord(id=asset_id, user_id=project.user_id, project_id=project.id,
                            task_id=task.id, kind=kind, output_key=output_key, name=name,
                            storage_key=key, metadata_json=metadata or {}, created_at=task.created_at)
        db.add(asset)
        db.flush()
        return asset

    def _archive_outputs(self, db, project, task):
        data = task.data
        if task.kind == "voice" and task.status == "completed":
            result = data.get("result", {})
            asset = self._asset(db, project, task, "voice_audio", "reference_audio", "音色参考音频",
                                path=result.get("reference_path"), url=result.get("preview_url"),
                                metadata={"sha256": result.get("reference_sha256"),
                                          "analysis": result.get("analysis", {})})
            if asset:
                vid = result.get("voice_id") or "custom_" + task.id
                if not db.get(VoiceRecord, vid):
                    description = data.get("request", {}).get("description") or result.get("description", "")
                    db.add(VoiceRecord(id=vid, user_id=project.user_id, asset_id=asset.id,
                                       name=description[:24] or "自定义音色", description=description,
                                       created_at=task.created_at))
        elif task.kind == "segment":
            planned = {s["segment_id"]: s for s in project.data.get("storyboard", {}).get("segments", [])}
            for segment in data.get("segments", []):
                if segment.get("status") != "completed":
                    continue
                sid = segment["segment_id"]
                shot_ids = segment.get("shot_ids", [])
                label = " / ".join(f"Shot {shot}" for shot in shot_ids) or sid
                plan = planned.get(sid, {})
                continuation_count = sum(1 for item in planned.values() if item.get("shot_ids") == shot_ids)
                if continuation_count > 1:
                    label += f" · 第 {plan.get('continuation_index', 1)} 段"
                self._asset(db, project, task, "shot_video", sid, label,
                            path=segment.get("normalized_av_path") or segment.get("raw_path"),
                            url=segment.get("video_url"), metadata={
                                "segment_id": sid, "shot_ids": shot_ids,
                                "continuation_index": plan.get("continuation_index", 1),
                                "duration_s": plan.get("duration_ms", 0) / 1000,
                                "voice_version": segment.get("voice_version"),
                                "prompt_hash": segment.get("prompt_hash")})
        elif task.kind == "render" and task.status == "completed":
            result = data.get("result", {})
            for variant, label in (("clean", "完整视频 · 原声版"), ("with_bgm", "完整视频 · 配乐版")):
                item = result.get(variant)
                if item:
                    self._asset(db, project, task, "final_video", variant, label,
                                path=item.get("local_path"), url=item.get("url"), metadata={
                                    "variant": variant, "duration_s": result.get("duration_s", 0),
                                    "version": result.get("version", 1), "mix_version": result.get("mix_version", 0)})

    def asset_path(self, storage_key):
        candidate = (self.asset_root / storage_key).resolve()
        if not candidate.is_relative_to(self.asset_root):
            raise ValueError("无效素材路径")
        return candidate

    def _public_asset(self, row):
        return {"id": row.id, "project_id": row.project_id, "task_id": row.task_id,
                "kind": row.kind, "name": row.name, "output_key": row.output_key,
                "url": "/assets/" + row.storage_key,
                "available": self.asset_path(row.storage_key).is_file(),
                "metadata": row.metadata_json, "created_at": iso(row.created_at)}

    def videos(self, username):
        with Session(self.engine) as db:
            rows = db.execute(select(AssetRecord, ProjectRecord)
                .join(ProjectRecord, AssetRecord.project_id == ProjectRecord.id)
                .join(User, AssetRecord.user_id == User.id)
                .where(User.username == username, AssetRecord.deleted_at.is_(None),
                       AssetRecord.kind.in_(["shot_video", "final_video"]))
                .order_by(AssetRecord.created_at.desc(), AssetRecord.id)).all()
            groups = {}
            for asset, project in rows:
                group = groups.setdefault(project.id, {
                    "project_id": project.id, "name": project.name,
                    "project_deleted": bool(project.deleted_at), "assets": []})
                group["assets"].append(self._public_asset(asset))
            return list(groups.values())

    def voices(self, username):
        with Session(self.engine) as db:
            rows = db.execute(select(VoiceRecord, AssetRecord).join(AssetRecord)
                .join(User, VoiceRecord.user_id == User.id)
                .where(User.username == username, VoiceRecord.deleted_at.is_(None), AssetRecord.deleted_at.is_(None))
                .order_by(VoiceRecord.created_at.desc())).all()
            return [{"voice_id": voice.id, "name": voice.name, "description": voice.description,
                     "preview_url": "/assets/" + asset.storage_key, "asset_id": asset.id,
                     "available": self.asset_path(asset.storage_key).is_file(),
                     "created_at": iso(voice.created_at)} for voice, asset in rows]

    def voice_for_selection(self, username, vid):
        with Session(self.engine) as db:
            row = db.execute(select(VoiceRecord, AssetRecord).join(AssetRecord)
                .join(User, VoiceRecord.user_id == User.id)
                .where(User.username == username, VoiceRecord.id == vid,
                       VoiceRecord.deleted_at.is_(None), AssetRecord.deleted_at.is_(None))).first()
            if not row:
                return None
            voice, asset = row
            path = self.asset_path(asset.storage_key)
            if not path.is_file():
                raise FileNotFoundError("音色文件不存在，请重新生成")
            return {"source": "custom", "voice_id": voice.id, "name": voice.name,
                    "description": voice.description, "reference_path": str(path),
                    "preview_url": "/assets/" + asset.storage_key,
                    "reference_sha256": asset.metadata_json.get("sha256") or hashlib.sha256(path.read_bytes()).hexdigest()}

    def edit_voice(self, username, vid, name=None, delete=False):
        with Session(self.engine) as db, db.begin():
            voice = db.scalar(select(VoiceRecord).join(User)
                .where(User.username == username, VoiceRecord.id == vid, VoiceRecord.deleted_at.is_(None)))
            if not voice:
                return False
            if delete:
                voice.deleted_at = utcnow()
            elif name is not None:
                voice.name = name
            return True

    def download_asset(self, username, aid):
        with Session(self.engine) as db:
            asset = db.scalar(select(AssetRecord).join(User)
                .where(User.username == username, AssetRecord.id == aid, AssetRecord.deleted_at.is_(None)))
            if asset:
                return self.asset_path(asset.storage_key), asset.name
            return None

    def import_legacy(self, root):
        """Idempotent import: never overwrite existing DB rows or resurrect deletion."""
        import json
        counts = {"projects": 0, "tasks": 0, "skipped": 0}
        for file in sorted((root / "projects").glob("p_*.json")):
            try:
                counts["projects"] += bool(self.save_project(json.loads(file.read_text(encoding="utf-8")), importing=True))
            except (ValueError, KeyError, OSError):
                counts["skipped"] += 1
                log.warning("Skipped invalid legacy project: %s", file.name)
        for folder, kind in (("voice_tasks", "voice"), ("segment_tasks", "segment"), ("render_tasks", "render")):
            for file in sorted((root / folder).glob("*.json")):
                try:
                    counts["tasks"] += bool(self.save_task(json.loads(file.read_text(encoding="utf-8")), kind, importing=True))
                except (ValueError, KeyError, OSError):
                    counts["skipped"] += 1
                    log.warning("Skipped invalid legacy task: %s", file.name)
        return counts

    def interrupt_unfinished(self):
        """Single-process MVP: preserve results, release stuck jobs for explicit retry."""
        with Session(self.engine) as db, db.begin():
            for row in db.scalars(select(TaskRecord).where(TaskRecord.status.in_(["generating", "rendering"]))):
                data = dict(row.data)
                data.update(status="failed", error="服务中断，已保留完成的结果，请重试未完成部分", message="任务已中断，可重试")
                for segment in data.get("segments", []):
                    if segment.get("status") in ("pending", "generating"):
                        segment.update(status="failed", error="服务中断，请重试")
                row.status, row.data, row.updated_at = "failed", data, utcnow()
            for row in db.scalars(select(ProjectRecord).where(ProjectRecord.deleted_at.is_(None))):
                data = dict(row.data)
                if data.get("status") in ("searching_references", "analyzing_references", "planning", "storyboarding", "generating", "composing"):
                    previous = data["status"]
                    data.update(status="failed", interrupted_stage=previous, message="服务中断，已保存进度，可继续或重试")
                    if previous == "composing":
                        data["render"] = {**data.get("render", {}), "status": "failed"}
                    row.status, row.data = "failed", data
