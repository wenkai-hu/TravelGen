# -*- coding: utf-8 -*-
"""登录注册接口（/api/auth/*）。

- 用户名唯一：DB 唯一索引兜底 + 注册前预检返回 409
- 密码：pbkdf2 加盐哈希（stdlib hashlib，不引入 bcrypt/passlib 依赖）
- 登录返回 token（后续项目归属等接口按需携带）
"""
import hashlib, hmac, secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .models import User

router = APIRouter(prefix="/api/auth", tags=["登录注册"])

# ponytail: 内存会话表（服务重启即失效），后续接口需要鉴权时再换 DB 会话表或 JWT
SESSIONS: dict[str, int] = {}

_PBKDF2_ITER = 100_000
_USERNAME_RE = r"^[\w一-龥.-]{2,50}$"  # 2-50 位：中文/字母/数字/._-


class RegisterRequest(BaseModel):
    username: str = Field(..., pattern=_USERNAME_RE)
    password: str = Field(..., min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


def _hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITER).hex()
    return f"{_PBKDF2_ITER}${salt}${digest}"


def _verify(password: str, stored: str) -> bool:
    try:
        iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters)).hex()
        return hmac.compare_digest(calc, digest)
    except ValueError:
        return False


@router.post("/register", status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_session)):
    username = req.username.strip()
    if await db.scalar(select(User).where(User.username == username)):
        raise HTTPException(409, detail={"code": "username_taken", "message": "用户名已存在", "detail": ""})
    db.add(User(username=username, password_hash=_hash(req.password)))
    await db.commit()
    return {"username": username}


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_session)):
    user = await db.scalar(select(User).where(User.username == req.username.strip()))
    if not user or not _verify(req.password, user.password_hash):
        raise HTTPException(401, detail={"code": "bad_credentials", "message": "用户名或密码错误", "detail": ""})
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = user.id
    return {"token": token, "username": user.username}


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
) -> str:
    """鉴权依赖：解析 Authorization: Bearer <token> → 当前用户名。缺失/无效 → 401。

    供 /api/projects/* 等需登录接口使用（Depends(get_current_user)）。
    SESSIONS 为内存表，服务重启后所有 token 失效，前端需重新登录。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, detail={"code": "not_authenticated", "message": "请先登录", "detail": ""})
    token = authorization.removeprefix("Bearer ").strip()
    user_id = SESSIONS.get(token)
    if user_id is None:
        raise HTTPException(401, detail={"code": "invalid_token", "message": "登录已失效，请重新登录", "detail": ""})
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(401, detail={"code": "invalid_token", "message": "登录已失效，请重新登录", "detail": ""})
    return user.username


if __name__ == "__main__":
    # 自检：哈希-校验往返（不依赖数据库）
    h = _hash("test-pass")
    assert _verify("test-pass", h) and not _verify("wrong-pass", h), "pbkdf2 往返失败"
    assert _verify("x", "garbage") is False, "损坏存储串应返回 False"
    print("auth 自检通过")
