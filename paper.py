# -*- coding: UTF-8 -*-
from typing import Tuple, Optional, Any, List

from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body, File, UploadFile

from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend
from starlette.responses import FileResponse

import sqlite3, time, jieba, os
import config, auth, folder, utils

router = APIRouter()


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

async def PaperDelete_(
        PID: int
) -> bool:
    params = (PID, )
    with sqlite3.connect(config.DB_PATH) as DBConn:
        # Step 1: Delete Relation Between Paper And Folder
        cursor = DBConn.execute("DELETE FROM Paper WHERE PID = ?", params)
        if cursor.rowcount == 0: return False

        # Step 2: Delete Metadata of Paper
        cursor = DBConn.execute("DELETE FROM Paper_Meta WHERE PID = ?", params)
        if cursor.rowcount == 0: return False

        # Step 3: Find Path of Paper Revision and delete them
        cursor = DBConn.execute("SELECT Path FROM Paper_Revision WHERE PID = ?", params)
        for row in cursor:
            paperPath = row[0]
            os.remove(paperPath)

        # Step 4: Delete Paper Revision Record in DB
        cursor = DBConn.execute("DELETE FROM Paper_Revision WHERE PID = ?", params)
        if cursor.rowcount == 0: return False

    return True


@router.post("/paper/import", tags=["users"])
async def paperImport(
        folder_info: folder.FolderInfo,
        file: UploadFile = File(...),
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
    start = time.time()
    try:
        res = await file.read()
        fileUploadPath = config.UPLOAD_PATH + utils.getNewUUID() + ".pdf"
        with open(fileUploadPath, "wb") as f:
            f.write(res)
        fid = list()
        fid.append(folder_info.FolderID)
        with sqlite3.connect(config.DB_PATH) as DBConn:
            DBConn.execute("INSERT INTO Paper(FID, Lock) VALUES (?, FALSE)", fid)
            cursor = DBConn.execute("SELECT MAX(PID) FROM Paper") # Thread unsafe
            pid = 0
            for r in cursor:
                pid = r[0]
                break
            params = [pid, session_data[1].username, time.time(), fileUploadPath]
            DBConn.execute("INSERT INTO Paper_Revision(PID, Edit_User, Edit_Time, Version, Path) VALUES (?, ?, ?, 0, ?)", params)
            return {"status": 200, "message": "Paper successfully imported.", 'time': time.time() - start, 'PID': pid}
    except Exception as e:
        return {"status": 400, "message": str(e), 'time': time.time() - start, 'filename': file.filename}


@router.post("/paper/folder", tags=["users"])
async def paperFolder(
        paper_folder_info: PaperMoveInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
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

# 自动解析，由前端请求另外一个接口，与当前程序无关
@router.post("/paper/metadata", tags=["users"])
async def paperMetadata(
        paper_meta: PaperMetaInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
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
    await auth.checkLogin(session_data)
    retValue = await PaperDelete_(paper.PaperID)
    if retValue:
        return {"status": 200, "message": "Paper deleted successfully."}
    else:
        return {"status": 202, "message": "Fail to delete paper."}



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
        query_type: List[str],
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
    keywordList = jieba.lcut(keywords)
    keywordList2 = []
    for kw in keywordList:
        if kw.strip() != '':
            keywordList2.append(kw.strip())

    if len(keywordList2) == 0:
        return {"status": 200, "message": "Paper queried successfully.", "pids": {}}

    PIDS = []
    with sqlite3.connect(config.DB_PATH) as DBConn:
        SQL = f"SELECT PID FROM Paper_Meta, Paper, User_Folder WHERE User_Folder.FID = Paper.FID And Paper.PID = Paper_Meta.PID AND UID = {session_data[1].userID} AND ("
        for qw in query_type:
            for kw in keywordList2:
                SQL += f"OR {qw} LIKE '%{kw}%' "
        SQL += ")"
        cursor = DBConn.execute(SQL)
        for row in cursor:
            PIDS.append(row[0])

    return {"status": 200, "message": "Paper queried successfully.", "pids": PIDS}


@router.post("/paper/lock", tags=["users"])
async def paperLock(
        paper: PaperInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = list()
    params.append(paper.PaperID)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT PID FROM Paper WHERE PID = ? AND Lock = false", params)
        pid = 0
        for r in cursor:
            pid = r[0]
            break
        if pid == paper.PaperID:
            params = (session_info[1].username, paper.PaperID)
            DBConn.execute("Update Paper SET Lock = true AND LockHolder = ? WHERE PID = ?", params)
            return {"status": 200, "message": "Paper locked successfully.", "lock_result": True}
        else:
            return {"status": 202, "message": "Fail to lock paper, it is locked already.", "lock_result": False}


@router.post("/paper/unlock", tags=["users"])
async def paperUnlock(
        paper: PaperInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = list()
    params.append(paper.PaperID)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT PID FROM PAPER WHERE PID = ? AND Lock = true", params)
        pid = 0
        for r in cursor:
            pid = r[0]
            break
        if pid == paper.PaperID:
            params = (paper.PaperID, session_info[1].username)
            cursor = DBConn.execute("Update Paper SET Lock = false WHERE PID = ? AND LockHolder = ?", params)
            if cursor.rowcount == 1:
                return {"status": 200, "message": "Paper unlocked successfully.", "unlock_result": True}
            else:
                return {"status": 202, "message": "Fail to unlock paper, the lockholder aren't you.",
                        "unlock_result": False}
        else:
            return {"status": 202, "message": "Fail to unlock paper, it is unlocked already.", "unlock_result": False}


@router.post("/paper/download", tags=["users"])
async def paperDownload(
        paper: PaperDownloadInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = list()
    params.append(paper.PaperID)
    params.append(paper.Version)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT PID, Path FROM Paper_Revision WHERE PID = ? AND Version = ?", params)
        pid = 0
        path = ""
        for r in cursor:
            pid = r[0]
            path = r[1]
            break
        if pid == paper.PaperID:
            return {"status": 200, "message": "Paper download successfully.", "address": path}
        else:
            return {"status": 202, "message": "Fail to download paper."}


# 此函数待讨论，我的意思是把现有版本同步到云端的操作。本函数还未加入接口说明中。
@router.post("/paper/upload", tags=["users"])
async def paperUpload(
        paper: PaperUploadInfo,
        file: UploadFile = File(...),
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    try:
        res = await file.read()
        fileUploadPath = config.UPLOAD_PATH + utils.getNewUUID() + ".pdf"  # Security
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
    await auth.checkLogin(session_info)
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
    await auth.checkLogin(session_info)
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
