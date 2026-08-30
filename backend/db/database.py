# -*- coding: utf-8 -*-
"""异步 SQLAlchemy 引擎与会话（MySQL）。

连接串读 experiments/config.json 的 db.async_url（含密码，该文件已被 gitignore）；
缺配置时启动即报错，避免静默连不上。
"""
import json, os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CONFIG_PATH = os.path.join(REPO, "experiments", "config.json")


def _db_url() -> str:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    url = (cfg.get("db") or {}).get("async_url", "")
    if not url:
        raise RuntimeError(f"{CONFIG_PATH} 缺少 db.async_url（MySQL 连接串，如 mysql+aiomysql://root:***@localhost:3306/travelgen）")
    return url

#创建数据库引擎
engine = create_async_engine(_db_url(),echo=True)
#创建实例session对象 后续依赖注入接口 让接口能够真正操作数据库
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass

#依赖注入函数
async def get_session() -> AsyncSession:
    """FastAPI 依赖：每请求一个会话，用完自动关闭。"""
    async with SessionLocal() as session:
        yield session

#建表函数
async def init_db():
    """启动时建表（幂等，表已存在则跳过）。"""
    from . import models  # noqa: F401  确保 User 注册进 Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
