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


class UserNameInfo(BaseModel):
    username: str


class FolderIDInfo(BaseModel):
    FolderID: int


@router.post("/admin/folder/list", tags=["users"])
async def folderList(
        user: UserNameInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    folder_list = list()
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    if role == 'user':
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated, you are not administrator."
        )
    param = [user.username]
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT Name, FID FROM Folder WHERE Username = ?", param)
        for row in cursor:
            folder = dict()
            folder['folderName'] = row[0]
            folder['FID'] = row[1]
            folder['own'] = True
            folder_list.append(folder)
        param_uid = list()
        UserID = DBConn.execute("SELECT UID FROM User WHERE Username = ?", param)
        for ID in UserID:
            param_uid.append(ID[0])
            break
        cursor = DBConn.execute("SELECT FID FROM User_Folder WHERE UID = ?", param_uid)
        for row in cursor:
            folder = dict()
            folder['folderName'] = row[0]
            folder['FID'] = row[1]
            folder['own'] = False
            param_fid = list()
            param_fid.append(row[1])
            flag = DBConn.execute("SELECT FID FROM Folder WHERE FID = ? AND Shared = True", param_fid)
            if flag.rowcount != 0:
                folder_list.append(folder)
            else:
                continue
        return {"status": 200, "message": "Folder listed successfully.", "folder_list": folder_list}


@router.post("/admin/folder/queryshared", tags=["users"])
async def folderQueryshared(
        folder: FolderIDInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    if role == 'user':
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated, you are not administrator."
        )
    with sqlite3.connect(config.DB_PATH) as DBConn:
        param = [folder.FolderID]
        cursor = DBConn.execute("SELECT FID, Shared FROM Folder WHERE FID = ?", param)
        for row in cursor:
            if row[0] == FolderIDInfo.FolderID:
                return {"status": 200, "message": "Folder query shared successfully.", "Shared": row[1]}
            else:
                return {"status": 202, "message": "Fail to folder query shared."}
