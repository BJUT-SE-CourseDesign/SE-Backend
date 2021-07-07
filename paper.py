# -*- coding: UTF-8 -*-
from typing import Tuple, Optional, Any

from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body, File, UploadFile

from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend

import sqlite3
import config
import hashlib
import auth
import folder
import time

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


# import和folder逻辑有问题，import时候该如何分配PID？
@router.post("/paper/import", tags=["users"])
async def paperImport(
        folder_info: folder.FolderInfo,
        file: UploadFile = File(...),
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    start = time.time()
    try:
        res = await file.read()
        fileUploadPath = config.UPLOAD_PATH + file.filename # Security
        with open(fileUploadPath, "wb") as f:
            f.write(res)
        fid = list()
        fid.append(folder_info.FolderID)
        DBConn.execute("INSERT INTO Paper(FID, Lock) VALUES (?, FALSE)", fid)
        cursor = DBConn.execute("SELECT MAX(PID) FROM Paper")
        pid = 0
        for r in cursor:
            pid = r[0]
            break
        params = [pid, session_info[1].username, time.time(), fileUploadPath]
        DBConn.execute("INSERT INTO Paper_Revision(PID, Edit_User, Edit_Time, Version, Path) VALUES (?, ?, ?, 0, ?)", params)
        return {"status": 200, "message": "Paper successfully imported.", 'time': time.time() - start, 'PID': pid}
    except Exception as e:
        return {"status": 400, "message": str(e), 'time': time.time() - start, 'filename': file.filename}


@router.post("/paper/folder", tags=["users"])
async def paperFolder(
        folder_info: folder.FolderInfo,
        paper_info: PaperInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    with sqlite3.connect(config.DB_PATH) as DBConn:
        fid = list()
        fid.append(folder_info.FolderID)
        DBConn.execute("INSERT INTO Paper(FID, Lock) VALUES (?, FALSE)", fid)
        pid = list()
        pid.append(paper_info.PaperID)
        DBConn.execute("INSERT INTO Paper_Meta(PID) VALUES (?)", pid)
        return {"status": 200, "message": "Paper imported successfully.", "pid": pid}


# 少自动解析
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
        DBConn.execute("DELETE FROM Paper WHERE PID = ?", pid)
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


@router.post("/paper/lock", tags=["users"])
async def paperLock(
        paper: PaperInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    params = list()
    params.append(paper.PaperID)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT PID FROM PAPER WHERE PID = ? AND Lock = false", params)
        if cursor.rowcount != 0:
            DBConn.execute("Update Paper SET Lock = true WHERE PID = ?", params)
            return {"status": 200, "message": "Paper locked successfully.", "lock_result": True}
        else:
            return {"status": 202, "message": "Fail to lock paper, it is locked already.", "lock_result": False}


# 未完成，问题在于如果没有锁的持有者，无法判断unlock可否执行
@router.post("/paper/unlock", tags=["users"])
async def paperUnlock(
        paper: PaperInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    params = list()
    params.append(paper.PaperID)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT PID FROM PAPER WHERE PID = ? AND Lock = true", params)
        if cursor.rowcount != 0:
            DBConn.execute("Update Paper SET Lock = false WHERE PID = ?", params)
            return {"status": 200, "message": "Paper unlocked successfully.", "unlock_result": True}
        else:
            return {"status": 202, "message": "Fail to unlock paper, it is unlocked already.", "unlock_result": False}

