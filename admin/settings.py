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


class SettingInfo(BaseModel):
    Key: str
    Value: int


@router.post("/admin/settings/query", tags=["users"])
async def adminSettingsQuery(
        Key: str,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
<<<<<<< Updated upstream
    await auth.checkLogin(session_info)
    await auth.needAdminRole(session_info)
    settings_list = dict()
    with sqlite3.connect(config.DB_PATH) as DBConn:
        value = 0
        param = [key_info.Key]
        cursor = DBConn.execute("SELECT Value FROM Setting WHERE Name = ?", param)
=======
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
        value = 0
        param = [Key]
        cursor = DBConn.execute("SELECT Name, Value FROM Setting WHERE Name = ?", param)
>>>>>>> Stashed changes
        for row in cursor:
            value = row[0]
        return {"status": 200, "message": "Settings queried successfully.", "value": value}


@router.post("/admin/settings/modify", tags=["users"])
async def adminSettingsModify(
        setting_info: SettingInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    await auth.needAdminRole(session_info)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = [setting_info.Value, setting_info.Key]
        cursor = DBConn.execute("UPDATE Setting SET Value = ? WHERE Name = ?", params)
        if cursor.rowcount == 1:
            return {"status": 200, "message": "Settings modified successfully."}
        else:
            return {"status": 202, "message": "Failed to modify settings."}


@router.post("/admin/settings/list", tags=["users"])
async def adminSettingsList(
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    await auth.needAdminRole(session_info)
    key_list = list()
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT Name FROM Setting")
        for row in cursor:
            key_list.append(row[0])
        return {"status": 200, "message": "Settings listed successfully.", "keyList": key_list}
