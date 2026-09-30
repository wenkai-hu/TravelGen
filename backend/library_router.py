"""Project management and personal library; generation remains in v1_router."""
import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from db.auth import get_current_user
from schemas import GenerateRequest
import projects as P
import v1_router as workflow

router = APIRouter(prefix="/api", tags=["项目与素材"])


def storage():
    if P.STORAGE is None:
        raise HTTPException(503, detail={"message": "数据库尚未就绪"})
    return P.STORAGE


class NamePatch(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DraftPatch(BaseModel):
    section: str = Field(pattern=r"^(input|plan|references|storyboard)$")
    data: dict | None = None


class NewDraft(BaseModel):
    request: dict = Field(default_factory=dict)


@router.post("/project-drafts", status_code=201)
async def create_draft(req: NewDraft, user: str = Depends(get_current_user)):
    project = P.Project(workflow._new_id("p"), req.request, username=user)
    project.status = "draft"
    P.PROJECTS[project.project_id] = project
    project.dump()
    return {"project_id": project.project_id}


@router.patch("/projects/{pid}/draft")
async def save_draft(pid: str, req: DraftPatch, user: str = Depends(get_current_user)):
    project = workflow._owned_project(pid, user)
    if req.section == "input":
        if project.status != "draft":
            workflow._err(409, "not_draft", "该项目已开始创作，请从项目页继续")
        previous_theme = project.request.get("theme") or "未命名项目"
        project.request = req.data or {}
        if project.name == previous_theme:
            project.name = project.request.get("theme") or "未命名项目"
    if req.data is None:
        project.draft.pop(req.section, None)
    else:
        project.draft[req.section] = req.data
    project.dump()
    return {"saved_at": project.updated_at}


@router.post("/projects/{pid}/start", status_code=202)
async def start_draft(pid: str, req: GenerateRequest, user: str = Depends(get_current_user)):
    project = workflow._owned_project(pid, user)
    if project.status != "draft":
        workflow._err(409, "not_draft", "项目已经开始，请继续原项目")
    return await workflow._start_project(req, user, project)


@router.patch("/projects/{pid}")
async def rename_project(pid: str, req: NamePatch, user: str = Depends(get_current_user)):
    project = workflow._owned_project(pid, user)
    if not req.name.strip():
        workflow._err(400, "invalid_name", "名称不能为空")
    project.name = req.name.strip()
    project.dump()
    return {"name": project.name}


@router.delete("/projects/{pid}")
async def delete_project(pid: str, user: str = Depends(get_current_user)):
    project = workflow._owned_project(pid, user)
    if project.status in ("searching_references", "analyzing_references", "planning", "storyboarding", "generating", "composing") or any(
        (task := P.load_any_task(tid)) and task.status in ("generating", "rendering")
        for tid in project.voice_tasks + project.segment_tasks + project.render_tasks
    ):
        workflow._err(409, "project_busy", "项目仍有任务在执行，请完成后再删除")
    project.deleted_at = P._now()
    project.dump()
    return {"deleted": True, "assets_retained": True}


@router.post("/projects/{pid}/retry", status_code=202)
async def retry_project(pid: str, user: str = Depends(get_current_user)):
    project = workflow._owned_project(pid, user)
    if project.status != "failed":
        workflow._err(409, "not_failed", "当前项目无需重试")
    stage = project.interrupted_stage
    if stage == "storyboarding" or (project.copywriting and not project.storyboard.get("scenes")):
        project.status = "storyboarding"
        job = workflow._run_storyboard(project)
    elif stage == "planning" or project.reference_assets:
        project.status = "planning"
        job = workflow._run_plan(project)
    else:
        project.status = "searching_references"
        job = workflow._run_reference_search(project)
    project.interrupted_stage = None
    project.dump()
    asyncio.create_task(job)
    return {"status": project.status}


@router.get("/library/videos")
def library_videos(user: str = Depends(get_current_user)):
    return {"groups": storage().videos(user)}


@router.get("/library/voices")
def library_voices(user: str = Depends(get_current_user)):
    return {"voices": storage().voices(user)}


@router.patch("/library/voices/{vid}")
def rename_voice(vid: str, req: NamePatch, user: str = Depends(get_current_user)):
    name = req.name.strip()
    if not name:
        workflow._err(400, "invalid_name", "名称不能为空")
    if not storage().edit_voice(user, vid, name=name):
        workflow._err(404, "voice_not_found", "音色不存在")
    return {"name": name}


@router.delete("/library/voices/{vid}")
def delete_voice(vid: str, user: str = Depends(get_current_user)):
    if not storage().edit_voice(user, vid, delete=True):
        workflow._err(404, "voice_not_found", "音色不存在")
    return {"deleted": True}


@router.get("/library/assets/{aid}/download")
def download_asset(aid: str, user: str = Depends(get_current_user)):
    result = storage().download_asset(user, aid)
    if not result or not result[0].is_file():
        workflow._err(404, "asset_not_found", "文件不存在或无权访问")
    path, name = result
    # Keep Content-Disposition filenames safe on Windows too.
    name = "".join(c for c in name if c not in '\\/:*?"<>|\r\n')
    return FileResponse(path, filename=name + Path(path).suffix)
