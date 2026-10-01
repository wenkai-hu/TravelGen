"""Run: .venv/Scripts/python -m unittest discover -s backend -p test_library_storage.py -v"""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import Session

import projects as P
import library_router as api
import v1_router as workflow
from db.database import Base
from db.library import Library
from db.models import User, AssetRecord, ProjectRecord, TaskRecord
from schemas import GenerateRequest, VoiceSelectionRequest


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.engine = create_engine("sqlite://")
        @event.listens_for(self.engine, "connect")
        def enable_fk(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db, db.begin():
            db.add_all([User(username="alice", password_hash="test"), User(username="bob", password_hash="test")])
        self.storage = Library(self.engine, self.root)
        self.previous_storage = P.STORAGE
        P.configure_storage(self.storage)
        self.project = P.Project("p_test", {"theme": "西湖", "duration_s": 20}, username="alice")
        P.PROJECTS[self.project.project_id] = self.project
        self.project.dump()

    def tearDown(self):
        P.configure_storage(self.previous_storage)
        self.engine.dispose()
        self.tmp.cleanup()

    def voice(self):
        file = self.root / "voice.wav"
        file.write_bytes(b"test-audio")
        task = P.VoiceTask("voice_test", self.project.project_id, {"description": "自然温柔的女声"})
        task.status = "completed"
        task.result = {"status": "candidate_ready", "voice_id": "custom_voice_test",
                       "reference_path": str(file), "reference_sha256": "same-voice"}
        task.dump()
        return task

    def video(self, task_id="st_one", success=True):
        file = self.root / f"{task_id}.mp4"
        file.write_bytes(b"test-video")
        task = P.SegmentTask(task_id, self.project.project_id, "single", {})
        task.status = "completed" if success else "failed"
        task.segments = [{"segment_id": "seg_001", "shot_ids": [1],
                          "status": task.status, "normalized_av_path": str(file)}]
        task.dump()
        return task

    def test_database_restore_preserves_draft_and_read_does_not_touch_time(self):
        asyncio.run(api.save_draft("p_test", api.DraftPatch(section="plan", data={"text": "写了一半"}), "alice"))
        updated = self.project.updated_at
        P.PROJECTS.clear()
        restored = P.load_project("p_test")
        self.assertEqual(restored.draft["plan"]["text"], "写了一半")
        self.assertEqual(restored.to_dict()["updated_at"], updated)
        self.assertEqual(self.storage.get_project("p_test")["updated_at"], updated)

    def test_outputs_auto_archive_once_and_failed_retry_keeps_success(self):
        task = self.video()
        task.dump()
        self.video("st_failed", False)
        groups = self.storage.videos("alice")
        self.assertEqual(len(groups[0]["assets"]), 1)
        self.assertTrue(groups[0]["assets"][0]["available"])
        self.assertEqual(groups[0]["assets"][0]["name"], "Shot 1")

    def test_cross_user_lists_selection_download_and_project_are_denied(self):
        self.voice()
        self.video()
        self.assertEqual(self.storage.voices("bob"), [])
        self.assertEqual(self.storage.videos("bob"), [])
        self.assertIsNone(self.storage.voice_for_selection("bob", "custom_voice_test"))
        asset_id = self.storage.voices("alice")[0]["asset_id"]
        self.assertIsNone(self.storage.download_asset("bob", asset_id))
        with self.assertRaises(HTTPException) as result:
            workflow._owned_project("p_test", "bob")
        self.assertEqual(result.exception.status_code, 404)

    def test_voice_reuse_after_source_project_deleted(self):
        self.voice()
        asyncio.run(api.delete_project("p_test", "alice"))
        other = P.Project("p_other", {}, username="alice")
        P.PROJECTS[other.project_id] = other
        other.dump()
        asyncio.run(workflow.select_voice("p_other", VoiceSelectionRequest(voice_id="custom_voice_test"), "alice"))
        self.assertEqual(other.voice["reference_sha256"], "same-voice")
        self.storage.edit_voice("alice", "custom_voice_test", delete=True)
        self.assertEqual(self.storage.voices("alice"), [])
        self.assertTrue(Path(other.voice["reference_path"]).is_file())

    def test_delete_project_retains_videos_and_does_not_resurrect_on_import(self):
        self.video()
        original = self.project.to_dict(include_private=True)
        asyncio.run(api.delete_project("p_test", "alice"))
        P.PROJECTS.clear()
        self.assertIsNone(P.load_project("p_test"))
        self.assertTrue(self.storage.videos("alice")[0]["project_deleted"])
        self.assertFalse(self.storage.save_project(original, importing=True))
        self.assertIsNone(self.storage.get_project("p_test"))

    def test_interrupted_task_keeps_completed_segments(self):
        task = self.video()
        task.status = "generating"
        task.segments.append({"segment_id": "seg_002", "shot_ids": [2], "status": "generating"})
        task.dump()
        self.project.status = "generating"
        self.project.dump()
        self.storage.interrupt_unfinished()
        P.configure_storage(self.storage)
        restored = P.load_segment_task(task.task_id)
        self.assertEqual(restored.status, "failed")
        self.assertEqual([s["status"] for s in restored.segments], ["completed", "failed"])
        self.assertEqual(P.load_project("p_test").interrupted_stage, "generating")
        self.assertEqual(len(self.storage.videos("alice")[0]["assets"]), 1)

    def test_two_video_versions_are_distinct_immutable_files(self):
        self.video("st_first")
        self.video("st_second")
        assets = self.storage.videos("alice")[0]["assets"]
        self.assertEqual(len(assets), 2)
        self.assertEqual(len({a["url"] for a in assets}), 2)

    def test_input_draft_and_resume_url(self):
        result = asyncio.run(api.create_draft(api.NewDraft(request={"city": "杭州"}), "alice"))
        project = P.load_project(result["project_id"])
        self.assertEqual(project.status, "draft")
        self.assertEqual(workflow.project_resume_url(project), f"/?draft={project.project_id}")
        project.copywriting = {"paragraphs": [{"text": "文案"}]}
        project.status = "waiting_confirm"
        self.assertEqual(workflow.project_resume_url(project), f"/plan/{project.project_id}")

    def test_legacy_import_is_idempotent_and_skips_orphan(self):
        folder = self.root / "legacy" / "projects"
        folder.mkdir(parents=True)
        payload = self.project.to_dict(include_private=True)
        payload["project_id"] = "p_legacy"
        (folder / "p_legacy.json").write_text(json.dumps(payload), encoding="utf-8")
        payload["project_id"], payload["username"] = "p_orphan", "missing-user"
        (folder / "p_orphan.json").write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(self.storage.import_legacy(folder.parent)["projects"], 1)
        self.assertEqual(self.storage.import_legacy(folder.parent)["projects"], 0)
        self.assertIsNone(self.storage.get_project("p_orphan"))

    def test_storage_path_traversal_rejected(self):
        self.assertIsNone(self.storage._key(url="/assets/../private.txt"))
        with self.assertRaises(ValueError):
            self.storage.asset_path("../private.txt")

    def test_start_uses_same_draft_project_without_creating_duplicate(self):
        self.project.status = "draft"
        self.project.dump()
        request = GenerateRequest(city="杭州", location="西湖", theme="西湖漫步", scene_type="景区推荐")
        with patch.object(workflow, "_run_reference_search", new_callable=AsyncMock):
            result = asyncio.run(api.start_draft("p_test", request, "alice"))
        self.assertEqual(result["project_id"], "p_test")
        self.assertEqual(len(self.storage.projects("alice")), 1)
        self.assertEqual(self.storage.get_project("p_test")["status"], "searching_references")

    def test_real_pipeline_save_hooks_archive_voice_video_and_render(self):
        wav = self.root / "generated.wav"
        wav.write_bytes(b"audio")
        voice = P.VoiceTask("voice_pipeline", "p_test", {"description": "自然女声"})
        voice.dump()
        with patch.object(workflow.runner, "seedance", None), patch.object(
            workflow.voice_sample_pipeline, "mock_candidate", return_value={
                "status": "candidate_ready", "voice_id": "custom_pipeline",
                "reference_path": str(wav), "reference_sha256": "voice-hash"}):
            asyncio.run(workflow._run_voice_task(self.project, voice))
        self.assertEqual(len(self.storage.voices("alice")), 1)
        self.project.storyboard = {"segments": [{"segment_id": "seg_001", "shot_ids": [1], "duration_ms": 20000}]}
        video = self.root / "generated.mp4"
        video.write_bytes(b"video")
        task = P.SegmentTask("st_pipeline", "p_test", "single", {})
        P.SEGMENT_TASKS[task.task_id] = task
        self.project.segment_tasks.append(task.task_id)
        self.project.dump()
        with patch.object(workflow.runner, "generate_segments", new_callable=AsyncMock, return_value=[{
            "segment_id": "seg_001", "shot_ids": [1], "status": "succeeded", "task_id": "provider-job-id",
            "normalized_av_path": str(video), "voice_version": 0, "voice_reference_sha256": None}]):
            asyncio.run(workflow._run_segment_task(self.project, task, ["seg_001"]))
        self.assertEqual(self.storage.get_task(task.task_id)["segments"][0]["external_task_id"], "provider-job-id")
        render = P.RenderTask("rt_pipeline", "p_test", {"voice_version": 0, "music_version": 0})
        with patch.object(workflow.composer, "compose_project", return_value={
            "status": "completed", "duration_s": 20, "version": 1,
            "clean": {"local_path": str(video)}, "with_bgm": {"local_path": str(video)}}):
            asyncio.run(workflow._run_render_task(self.project, render))
        self.assertEqual(self.storage.get_project("p_test")["status"], "completed")
        self.assertEqual(len(self.storage.videos("alice")[0]["assets"]), 3)

    def test_failed_voice_download_resumes_existing_seedance_task(self):
        voice = P.VoiceTask("voice_resume", "p_test", {"description": "活力小男孩"})
        voice.status = "failed"
        voice.result = {"seedance_task_id": "cpt-existing"}
        voice.error = "URLError: SSL EOF"
        voice.dump()
        self.project.voice_tasks.append(voice.task_id)
        self.project.dump()

        with patch.object(workflow, "_run_voice_task", new_callable=AsyncMock) as run:
            result = asyncio.run(workflow.create_voice_candidate(
                "p_test", workflow.VoiceCandidateRequest(description="活力小男孩"), "alice"))
        self.assertTrue(result["resumed"])
        self.assertEqual(result["task_id"], voice.task_id)
        self.assertEqual(self.project.voice_tasks, [voice.task_id])
        self.assertEqual(run.await_count, 1)

        wav = self.root / "resumed.wav"
        wav.write_bytes(b"audio")
        with patch.object(workflow.runner, "seedance", {"model": "test"}), \
                patch.object(workflow.ark_client, "submit_safe") as submit, \
                patch.object(workflow.ark_client, "get_task_safe",
                             return_value=("succeeded", "https://video.example.com/file.mp4", None)) as poll, \
                patch.object(workflow.ark_client, "download", return_value=5), \
                patch.object(workflow.voice_sample_pipeline, "finalize", return_value={
                    "status": "candidate_ready", "voice_id": "custom_resume",
                    "reference_path": str(wav), "reference_sha256": "voice-hash"}):
            asyncio.run(workflow._run_voice_task(self.project, voice))
        submit.assert_not_called()
        self.assertEqual(poll.call_args.args[1], "cpt-existing")
        self.assertEqual(voice.status, "completed")


if __name__ == "__main__":
    unittest.main()
