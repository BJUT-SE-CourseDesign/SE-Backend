# -*- coding: UTF-8 -*-
from typing import Tuple, Optional, Any

from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body, File, UploadFile

from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend

import sqlite3
import config, utils, auth, folder

router = APIRouter()


class AdminModifyUserPasswordInfo(BaseModel):
    username: str
    newPassword: str


class AdminUserNameInfo(BaseModel):
    username: str


@router.get("/admin/user/list", tags=["users"])
async def adminUserList(
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    await auth.needAdminRole(session_info)

    user_list = list()
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT Username FROM User WHERE Role = 'user'")
        for row in cursor:
            user_list.append(row[0])
    return {"status": 200, "message": "You are logged in.", "user_list": user_list}


@router.post("/admin/user/modifypassword", tags=["users"])
async def adminUserModifyPassword(
    user: AdminModifyUserPasswordInfo,
    session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    await auth.needAdminRole(session_info)
    # Authentication: Password is MD5 Digested
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = (utils.MD5(user.newPassword), user.username)
        cursor = DBConn.execute("UPDATE User SET Password = ? WHERE Username = ?", params)
        if cursor.rowcount == 1:
            return {"status": 200, "message": "Password modified successfully.", "result": True}
        else:
            return {"status": 202, "message": "Fail to modify password.", "result": False}


@router.post("/admin/user/delete", tags=["users"])
async def adminUserDelete(
    user: AdminUserNameInfo,
    session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    await auth.needAdminRole(session_info)

    with sqlite3.connect(config.DB_PATH) as DBConn:
        param = (user.username, )
        cursor = DBConn.execute("SELECT FID FROM Folder WHERE Username = ?", param)
        for row in cursor:
            fid = row[0]
            await folder.FolderDelete_(fid)
            
        cursor = DBConn.execute("DELETE FROM User WHERE Username = ?", param)
        if cursor.rowcount == 1:
            return {"status": 200, "message": "User delete successfully.", "result": True}
        else:
            return {"status": 202, "message": "Fail to delete user.", "result": False}
