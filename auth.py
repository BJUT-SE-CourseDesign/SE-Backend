# -*- coding: UTF-8 -*-
from typing import Tuple, Optional, Any

from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body

from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend

import sqlite3
import config
import hashlib
import uuid

router = APIRouter()


class SessionData(BaseModel):
    username: str
    role: str


class UserInfo(BaseModel):
    username: str
    password: str


class ModifyPasswordUserInfo(BaseModel):
    oldPassword: str
    newPassword: str


curSession = SessionCookie(
    name="session",
    secret_key=config.SESSION_SECRET_KEY,
    backend=InMemoryBackend(),
    data_model=SessionData,
    auto_error=False
)


@router.post("/users/login", tags=["users"])
async def userLogin(
        user: UserInfo,
        response: Response,
        session_info: Optional[SessionInfo] = Depends(curSession)
):
    old_session = None
    if session_info:
        old_session = session_info[0]

    # Authentication: Password is MD5 Digested
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = (user.username, hashlib.md5(user.password.encode(encoding='UTF-8')).hexdigest())
        cursor = DBConn.execute("SELECT Username, Role FROM User WHERE Username = ? and Password = ?", params)
        userFinded = False
        role = ""
        for row in cursor:
            userFinded = True
            role = row[1]
            break

    if userFinded:
        userSessionData = SessionData(username=user.username, role=role)
        await curSession.create_session(userSessionData, response, old_session)
        return {"status": 200, "message": "Logged in successfully.", "user": userSessionData}
    else:
        return {"status": 403, "message": "Username or password is wrong."}


@router.post("/users/logout", tags=["users"])
async def userLogout(
        response: Response,
        session_info: Optional[SessionInfo] = Depends(curSession)
):
    if not session_info:
        raise HTTPException(
            status_code=403,
            detail="Not authenticated"
        )
    await curSession.end_session(session_info[0], response)
    return {"status": 200, "message": "You have logged out now.", "user": session_info}


@router.get("/users/status", tags=["users"])
async def userStatus(
        session_data: Optional[SessionInfo] = Depends(curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    return {"status": 200, "message": "You are logged in.", "user": session_data}


@router.post("/users/register", tags=["users"])
async def userRegister(
        user: UserInfo
):
    # Authentication: Password is MD5 Digested
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params_name = list()
        params_folder_info = list()
        params_name.append(user.username)
        params_folder_info.append(str(uuid.uuid4()))
        params_folder_info.append(user.username)
        cursor = DBConn.execute("SELECT Username FROM User WHERE Username = ?", params_name)
        userFinded = False
        for row in cursor:
            userFinded = True
            break

        params = (user.username, hashlib.md5(user.password.encode(encoding='UTF-8')).hexdigest())
        if userFinded:
            return {"status": 202, "message": "User name already exists."}
        else:
            DBConn.execute("INSERT INTO User(Username, Password, Role) VALUES (?, ?, 'user')", params)
            DBConn.execute("INSERT INTO Folder(FUUID, Name, Username, Shared) VALUES (?, '我的文件夹', ?, FALSE)", params_folder_info)
            UID = DBConn.execute("SELECT UID FROM User WHERE Username = ?", params_name)
            FID = DBConn.execute("SELECT FID FROM Folder WHERE Username = ?", params_name)
            params_uid_fid = []
            for uid in UID:
                params_uid_fid.append(uid[0])
                break
            for fid in FID:
                params_uid_fid.append(fid[0])
                break
            DBConn.execute("INSERT INTO User_Folder(UID, FID) VALUES (?, ?)", params_uid_fid)
            return {"status": 200, "message": "Registered successfully."}


@router.post("/users/modifypassword", tags=["users"])
async def userModifyPassword(
    user: ModifyPasswordUserInfo,
    response: Response,
    session_info: Optional[SessionInfo] = Depends(curSession)
):
    if session_info is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )
    # Authentication: Password is MD5 Digested
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = (hashlib.md5(user.newPassword.encode(encoding='UTF-8')).hexdigest(), session_info[1].username,
                                    hashlib.md5(user.oldPassword.encode(encoding='UTF-8')).hexdigest())
        if params[0] == params[2]:
            return {"status": 202, "message": "Password modified unsuccessfully, the old password is identical to the new password."}

        cursor = DBConn.execute("UPDATE User SET Password = ? WHERE Username = ? AND Password = ?", params)
        if cursor.rowcount == 1:
            return {"status": 200, "message": "Password modified successfully."}
        else:
            return {"status": 202, "message": "Password modified unsuccessfully, the old password is wrong."}
