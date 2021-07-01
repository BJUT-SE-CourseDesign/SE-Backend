# -*- coding: UTF-8 -*-
from typing import Tuple, Optional, Any

from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body

from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend

import sqlite3
import config
import hashlib
import auth
import folder

router = APIRouter()


class PaperInfo(BaseModel):
    PaperID: int


class PaperMetaInfo(BaseModel):
    PaperID: int
    Title: str
    Authors: str
    Conference: str
    Abstract: str
    Keywords: str
    Year: int


@router.post("/paper/import", tags=["users"])
async def paperImport(
        folder: folder.FolderInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    with sqlite3.connect(config.DB_PATH) as DBConn:
        fid = list()
        fid.append(folder.FolderID)
        DBConn.execute("INSERT INTO Paper(FID, Lock) VALUES (?, FALSE)", fid)
        PID = DBConn.execute("SELECT MAX(PID) FROM Paper WHERE FID = ?", fid)
        pid = list()
        for p in PID:
            pid.append(p[0])
            break
        DBConn.execute("INSERT INTO Paper_Meta(PID) VALUES (?)", pid)
        return {"status": 200, "message": "Paper imported successfully.", "pid": pid}


@router.post("/paper/folder", tags=["users"])
async def paperFolder(
        folder: folder.FolderInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    with sqlite3.connect(config.DB_PATH) as DBConn:
        fid = list()
        fid.append(folder.FolderID)
        DBConn.execute("INSERT INTO Paper(FID, Lock) VALUES (?, FALSE)", fid)
        PID = DBConn.execute("SELECT MAX(PID) FROM Paper WHERE FID = ?", fid)
        pid = list()
        for p in PID:
            pid.append(p[0])
            break
        DBConn.execute("INSERT INTO Paper_Meta(PID) VALUES (?)", pid)
        return {"status": 200, "message": "Paper imported successfully.", "pid": pid}


@router.post("/paper/metadata", tags=["users"])
async def paperMetadata(
        paper_meta: PaperMetaInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = [paper_meta.Title, paper_meta.Authors, paper_meta.Conference, paper_meta.Abstract,
                  paper_meta.Keywords, paper_meta.Year, paper_meta.PaperID]
        DBConn.execute("UPDATE Paper_Meta SET Title = ?, Authors = ?, Conference = ?, Abstract = ?, Keywords = ?, Year = ? WHERE PID = ?", params)
        return {"status": 200, "message": "Paper Meta updated successfully.", "pid": paper_meta.PaperID}


# 需要修改数据库中对于外键的设置
@router.post("/paper/delete", tags=["users"])
async def paperDelete(
        paper: PaperInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    pid = list()
    pid.append(paper.PaperID)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        DBConn.execute("DELETE Paper WHERE PID = ?", pid)
        return {"status": 200, "message": "Paper deleted successfully.", "pid": pid[0]}


# 未完成：需要加入分词处理

# 4. 文献查询：在窗口右上部的文本框里填写搜索关键字；在文献标题、作者、关键字中进行搜索；查询的内容在窗口中部展示
# Path：/paper/query
# **前置条件：登录成功
# **参数：搜索关键字集合”keywords”[]、搜索分类集合”types” [“title”, ”author”, ”keyword”]
# **返回：匹配成功文献PID
@router.post("/paper/query", tags=["users"])
async def paperQuery(
        paper: PaperInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    pids = list()
    with sqlite3.connect(config.DB_PATH) as DBConn:
        return {"status": 200, "message": "Paper queried successfully.", "pids": pids}



