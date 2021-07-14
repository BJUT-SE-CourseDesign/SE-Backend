# -*- coding: UTF-8 -*-
from typing import Tuple, Optional, Any

from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body

from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend

import sqlite3, uuid
import config, utils

router = APIRouter()


class SessionData(BaseModel):
    userID: int
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
    auto_error=False,
    secure=True,
    samesite='None'
)


async def checkLogin(
        session_data: Optional[SessionInfo] = Depends(curSession)
):
    if session_data is None:
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated"
        )


async def needAdminRole(
        session_data: Optional[SessionInfo] = Depends(curSession)
):
    if session_data[1].role == 'user':
        raise HTTPException(
            status_code=403,
            detail="Not Authenticated, you are not administrator."
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
        params = (user.username, utils.MD5(user.password))
        cursor = DBConn.execute("SELECT UID, Username, Role FROM User WHERE Username = ? and Password = ?", params)
        userFinded = False
        Role = ""
        UID = 0
        Username = ""
        for row in cursor:
            userFinded = True
            UID = row[0]
            Username = row[1]
            Role = row[2]
            break
    if userFinded:
        userSessionData = SessionData(userID=UID, username=Username, role=Role)
        await curSession.create_session(userSessionData, response, old_session)
        return {"status": 200, "message": "Logged in successfully.", "user": userSessionData}
    else:
        return {"status": 403, "message": "Username or password is wrong."}


@router.post("/users/logout", tags=["users"])
async def userLogout(
        response: Response,
        session_info: Optional[SessionInfo] = Depends(curSession)
):
    await checkLogin(session_info)
    await curSession.end_session(session_info[0], response)
    return {"status": 200, "message": "You have logged out now.", "user": session_info}


@router.get("/users/status", tags=["users"])
async def userStatus(
        session_data: Optional[SessionInfo] = Depends(curSession)
):
    await checkLogin(session_data)
    return {"status": 200, "message": "You are logged in.", "user": session_data}


@router.post("/users/register", tags=["users"])
async def userRegister(
        user: UserInfo
):
    regEn = 0
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT Value FROM Settings WHERE Name = 'RegisterEnabled'")
        for row in cursor:
            regEn = row[0]
            break
    if regEn == 0:
        return {"status": 403, "message": "Registration Closed."}


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

        params = (user.username, utils.MD5(user.password))
        if userFinded:
            return {"status": 202, "message": "User name already exists."}
        else:
            DBConn.execute("INSERT INTO User(Username, Password, Role) VALUES (?, ?, 'user')", params)
            DBConn.execute("INSERT INTO Folder(FUUID, Name, Username, Shared) VALUES (?, '默认文件夹', ?, FALSE)", params_folder_info)
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
    session_info: Optional[SessionInfo] = Depends(curSession)
):
    await checkLogin(session_info)
    # Authentication: Password is MD5 Digested
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = (utils.MD5(user.newPassword), session_info[1].username, utils.MD5(user.oldPassword))
        if params[0] == params[2]:
            return {"status": 201, "message": "Password modification failed, the old password is identical to the new password."}

        cursor = DBConn.execute("UPDATE User SET Password = ? WHERE Username = ? AND Password = ?", params)
        if cursor.rowcount == 1:
            return {"status": 200, "message": "Password modified successfully."}
        else:
            return {"status": 202, "message": "Password modification failed, the old password is wrong."}


@router.post("/users/isadmin", tags=["users"])
async def userIsAdmin(
    session_info: Optional[SessionInfo] = Depends(curSession)
):
    await checkLogin(session_info)
    if session_info[1].role == 'user':
        return {"status": 200, "message": "Is user.", "flag": False}
    else:
        return {"status": 200, "message": "Is admin.", "flag": True}
