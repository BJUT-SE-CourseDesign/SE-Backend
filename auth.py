from typing import Tuple, Optional, Any

from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body

from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend

import sqlite3
import config
import hashlib

router = APIRouter()

class SessionData(BaseModel):
    username: str
    role: str

class UserInfo(BaseModel):
    username: str
    password: str


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
    # TODO
    return {"message": 'Not implemented'}
