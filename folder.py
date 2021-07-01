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
import uuid

router = APIRouter()


class FolderInfo(BaseModel):
    FolderID: int
    folderName: str
    shared: bool


class addFolderInfo(BaseModel):
    folderName: str
    shared: bool


# 在添加一个文件夹的时候，需要选择是否共享
@router.post("/folder/add", tags=["users"])
async def userAddFolder(
        folder: addFolderInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    params = [str(uuid.uuid4()), folder.folderName, session_info[1].username, folder.shared]
    with sqlite3.connect(config.DB_PATH) as DBConn:
        DBConn.execute("INSERT INTO Folder(FUUID, Name, Username, Shared) VALUES (?, ?, ?, ?)", params)
        FID = DBConn.execute("SELECT MAX(FID) FROM Folder WHERE FUUID = ? AND Name = ? AND Username = ? AND Shared = ?", params)
        fid = list()
        for f in FID:
            fid.append(f[0])
            break
        return {"status": 200, "message": "Folder added successfully.", "fid": fid}


@router.get("/folder/list", tags=["users"])
async def userListFolder(
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    folder_list = list()
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    param = [session_info[1].username]
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT Name, FID FROM Folder WHERE Username = ?", param)
        for row in cursor:
            folder = dict()
            folder['folderName'] = row[0]
            folder['FID'] = row[1]
            folder_list.append(folder)
        return {"status": 200, "message": "Folder listed successfully.", "folderList": folder_list}
