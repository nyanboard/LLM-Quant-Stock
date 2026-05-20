"""
api/main.py — uvicorn 入口

uvicorn 查找 api.main:app，本文件 re-export api 包中的 app 实例。
"""
from api import app  # noqa: F401
