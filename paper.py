# -*- coding: UTF-8 -*-
from typing import Tuple, Optional, Any

from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body, File, UploadFile

from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend
from starlette.responses import FileResponse

import sqlite3
import config
import hashlib
import auth
import folder
import time
import jieba

router = APIRouter()
types = {"Title": 1, "Authors": 2, "Conference": 3, "Abstract": 4, "Keywords": 5, "Year": 6}


class PaperInfo(BaseModel):
    PaperID: int


class PaperMoveInfo(BaseModel):
    old_folderID: int
    new_folderID: int
    PaperID: int


class PaperMetaInfo(BaseModel):
    PaperID: int
    Title: str
    Authors: str
    Conference: str
    Abstract: str
    Keywords: str
    Year: int


class PaperDownloadInfo(BaseModel):
    PaperID: int
    Version: int


class PaperUploadInfo(BaseModel):
    PaperID: int


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
        with sqlite3.connect(config.DB_PATH) as DBConn:
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
        paper_folder_info: PaperMoveInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = list()
        params.append(paper_folder_info.new_folderID)
        params.append(paper_folder_info.PaperID)
        params.append(paper_folder_info.old_folderID)
        cursor = DBConn.execute("UPDATE Paper SET FID = ? WHERE PID = ? AND FID = ?", params)
        if cursor.rowcount == 1:
            return {"status": 200, "message": "Paper moved successfully.", "flag": True}
        else:
            return {"status": 202, "message": "Fail to move paper.", "flag": False}

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
        cursor = DBConn.execute("DELETE FROM Paper WHERE PID = ?", pid)
        if cursor.rowcount == 1:
            return {"status": 200, "message": "Paper deleted successfully.", "pid": pid[0]}
        else:
            return {"status": 202, "message": "Fail to delete paper.", "pid": pid[0]}

# 未完成：需要加入分词处理，完善数据库查询语句（真的不会写了我服了这啥啊），目前只用了最笨的办法写了title的查询
# 这里我其实是想卷的，加入Query纠错，查询还有同义词替换，不知道可行度如何
# 4. 文献查询：在窗口右上部的文本框里填写搜索关键字；在文献标题、作者、关键字中进行搜索；查询的内容在窗口中部展示
# Path：/paper/query
# **前置条件：登录成功
# **参数：搜索关键字集合”keywords”[]、搜索分类集合”types” [“title”, ”author”, ”keyword”]
# **返回：匹配成功文献PID
@router.post("/paper/query", tags=["users"])
async def paperQuery(
        keywords: str,
        query_type: str,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    pids = list()
    flag = False
    keywords_list = list()
    query_t = types[query_type]
    for ch in keywords.decode('utf-8'):
        if u'\u4e00' <= ch <= u'\u9fff':
            flag = True
    if flag:
        keywords_list = keywords.split(' ')
    else:
        keywords_list = keywords.split(',')
    with sqlite3.connect(config.DB_PATH) as DBConn:
        if query_t == 1:
            for k in keywords_list:
                param = list()
                param.append(k)
                cursor = DBConn.execute("SELECT PID FROM Paper_Meta WHERE Title LIKE '%?%'", param)
                for row in cursor:
                    if row[0] not in pids:
                        pids.append(row[0])
        elif query_t == 2:
            cursor = DBConn.execute("SELECT * FROM Paper_Meta WHERE Authors LIKE '%?%'")
        elif query_t == 3:
            cursor = DBConn.execute("SELECT * FROM Paper_Meta WHERE Conference LIKE '%?%'")
        elif query_t == 4:
            cursor = DBConn.execute("SELECT * FROM Paper_Meta WHERE Abstract LIKE '%?%'")
        elif query_t == 55:
            cursor = DBConn.execute("SELECT * FROM Paper_Meta WHERE Keywords LIKE '%?%'")
        elif query_t == 6:
            cursor = DBConn.execute("SELECT * FROM Paper_Meta WHERE Year LIKE '%?%'")

        return {"status": 200, "message": "Paper queried successfully.", "pids": pids}


# 未完成，目的为根据关键词对于所有文献进行排序
@router.post("/paper/sort", tags=["users"])
async def paperSort(
        keywords: str,
        types: str,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    pids = list()
    jieba.cut(keywords)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT * FROM Paper_Meta WHERE Title LIKE '%KeyWord%' or Authors LIKE '%KeyWord%' or Year LIKE '%KeyWord%' or ...")
        return {"status": 200, "message": "Paper sorted successfully.", "pids": pids}


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
        pid = 0
        for r in cursor:
            pid = r[0]
            break
        if pid == paper.PaperID:
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
        pid = 0
        for r in cursor:
            pid = r[0]
            break
        if pid == paper.PaperID:
            DBConn.execute("Update Paper SET Lock = false WHERE PID = ?", params)
            return {"status": 200, "message": "Paper unlocked successfully.", "unlock_result": True}
        else:
            return {"status": 202, "message": "Fail to unlock paper, it is unlocked already.", "unlock_result": False}


# 未完成
@router.post("/paper/download", tags=["users"])
async def paperDownload(
        paper: PaperDownloadInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    params = list()
    params.append(paper.PaperID)
    params.append(paper.Version)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT PID FROM Paper_Revision WHERE PID = ? AND Version = ?", params)
        pid = 0
        for r in cursor:
            pid = r[0]
            break
        if pid == paper.PaperID:
            # 缺下载的代码，俺不太会，找了半天没找明白
            return {"status": 200, "message": "Paper download successfully.", "adress": 0}
        else:
            return {"status": 202, "message": "Fail to download paper."}


# 此函数待讨论，我的意思是把现有版本同步到云端的操作。本函数还未加入接口说明中。
@router.post("/paper/upload", tags=["users"])
async def paperUpload(
        paper: PaperUploadInfo,
        file: UploadFile = File(...),
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    try:
        res = await file.read()
        fileUploadPath = config.UPLOAD_PATH + file.filename  # Security
        with open(fileUploadPath, "wb") as f:
            f.write(res)

        with sqlite3.connect(config.DB_PATH) as DBConn:
            params = list()
            version = 0
            params.append(paper.PaperID)
            cursor_version = DBConn.execute("SELECT MAX(Version) FROM Paper_Revision WHERE PID = ?", params)
            for r in cursor_version:
                version = r[0]
                break
            params.append(session_info[1].username)
            params.append(time.time())
            params.append(version+1)
            params.append(fileUploadPath)
            params.append(paper.PaperID)
            DBConn.execute("INSERT INTO Paper_Revision SET Edit_User = ?, Edit_Time = ?, Version = ?, Path = ? WHERE PID = ?", params)
            return {"status": 200, "message": "Paper upload successfully.",
                    "info": {"PID": paper.PaperID, "editUser": param[0], "editTime": param[1], "version": param[2]}}
    except Exception as e:
        return {"status": 400, "message": str(e), "PID": paper.PaperID}


@router.post("/paper/list", tags=["users"])
async def paperList(
        paper: PaperDownloadInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    versionList = list()
    param = list()
    param.append(paper.PaperID)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT Edit_User, Edit_Time, Version FROM Paper_Revision WHERE PID = ? ORDER BY Version DESC", param)
        for row in cursor:
            versionList.append({"editUser": row[0], "editTime": row[1], "version": row[2]})
        return {"status": 200, "message": "Paper listed successfully.", "version_list": versionList}


@router.post("/paper/all", tags=["users"])
async def paperAll(
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    param = list()
    param.append(session_info[1].username)
    pids = list()
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT FID FROM Folder WHERE Username = ?", param)
        for row in cursor:
            fid = list()
            fid.append(row[0])
            cur = DBConn.execute("SELECT PID FROM Paper WHERE FID = ?", fid)
            for r in cur:
                pids.append(r[0])
        return {"status": 200, "message": "Paper all successfully.", "pids": pids}
