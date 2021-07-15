# -*- coding: UTF-8 -*-
from typing import Tuple, Optional, Any
from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body

from fastapi_sessions import SessionCookie, SessionInfo

import sqlite3
import config, auth, utils, paper

router = APIRouter()


class FolderInfo(BaseModel):
    FolderID: int
    folderName: str
    shared: bool


class FolderAddInfo(BaseModel):
    folderName: str
    shared: bool


class FolderDeleteInfo(BaseModel):
    FolderID: int


class FolderRenameInfo(BaseModel):
    FolderID: int
    newFolderName: str


class FolderShareInfo(BaseModel):
    FolderID: int


class FolderJoinInfo(BaseModel):
    FUUID: str


class FolderSharedMemberInfo(BaseModel):
    UserName: str


async def FolderDelete_(
        folderID: int
):
    with sqlite3.connect(config.DB_PATH) as DBConn:
        param = (folderID, )
        papers = DBConn.execute("SELECT PID FROM Paper WHERE FID = ?", param)
        for row in papers:
            PID = row[0]
            await paper.PaperDelete_(PID)
        DBConn.execute("DELETE FROM Folder WHERE FID = ?", param)


# 在添加一个文件夹的时候，需要选择是否共享
@router.post("/folder/add", tags=["users"])
async def folderAdd(
        folder: FolderAddInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = [utils.getNewUUID(), folder.folderName, session_info[1].username, folder.shared]
    with sqlite3.connect(config.DB_PATH) as DBConn:
        DBConn.execute("INSERT INTO Folder(FUUID, Name, Username, Shared) VALUES (?, ?, ?, ?)", params)
        FID = DBConn.execute("SELECT MAX(FID) FROM Folder WHERE FUUID = ? AND Name = ? AND Username = ? AND Shared = ?", params) # Thread Unsafe
        fid = list()
        for f in FID:
            fid.append(f[0])
            break
        return {"status": 200, "message": "Folder added successfully.", "fid": fid}


@router.post("/folder/delete", tags=["users"])
async def folderDelete(
        folder: FolderDeleteInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = [folder.FolderID, session_info[1].username]
    param = [session_info[1].username]
    paper_num = 0
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT FID FROM Folder WHERE Username = ?", param)
        for row in cursor:
            paper_num = paper_num + 1
        if paper_num <= 1:
            return {"status": 201, "message": "Failed to delete folder, only one left.", "delete_result": False}

        flag = False
        cursor = DBConn.execute("SELECT FID FROM Folder WHERE FID = ? AND Username = ?", params)
        for row in cursor:
            flag = True
            break
        if flag == False:
            return {"status": 202, "message": "Failed to delete folder, this folder does not belong to you.", "delete_result": False}
        else:
            await FolderDelete_(folder.FolderID)
            return {"status": 200, "message": "Folder deleted successfully.", "delete_result": True}


@router.get("/folder/list", tags=["users"])
async def folderList(
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    folder_list = list()
    param = list()
    param.append(session_info[1].username)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT Name, FID, Shared FROM Folder WHERE Username = ?", param)
        for row in cursor:
            folder = dict()
            folder['folderName'] = row[0]
            folder['FID'] = row[1]
            folder['shared'] = row[2]
            folder['own'] = True
            folder_list.append(folder)

        cursor = DBConn.execute("SELECT FID FROM User_Folder WHERE UID = ?", param)
        for row in cursor:
            param_fid = [row[0]]
            cursor2 = DBConn.execute("SELECT Name, FID, Shared FROM Folder WHERE FID = ? AND Shared = TRUE", param_fid)
            for r in cursor2:
                folder = dict()
                folder['folderName'] = r[0]
                folder['FID'] = r[1]
                folder['shared'] = r[2]
                folder['own'] = False
                folder_list.append(folder)
            else:
                continue
        return {"status": 200, "message": "Folder listed successfully.", "folder_list": folder_list}


@router.post("/folder/listpaper", tags=["users"])
async def folderListpaper(
        folder: FolderDeleteInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    param = [folder.FolderID]
    pids = list()
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT PID FROM Paper WHERE FID = ?", param)
        for row in cursor:
            pids.append(row[0])
        return {"status": 200, "message": "Listed paper in folder.", "pids": pids}


@router.post("/folder/rename", tags=["users"])
async def folderRename(
        folder: FolderRenameInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = [folder.newFolderName, folder.FolderID, session_info[1].username]
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("UPDATE Folder SET Name = ? WHERE FID = ? AND Username = ?", params)
        if cursor.rowcount == 1:
            return {"status": 200, "message": "Folder renamed successfully.", "FID": folder.FolderID}
        else:
            return {"status": 202, "message": "Fail to rename folder.", "FID": folder.FolderID}


@router.post("/folder/share", tags=["users"])
async def folderShare(
        folder: FolderShareInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = [folder.FolderID, session_info[1].username]
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT FUUID FROM Folder WHERE FID = ? AND Username = ?", params)
        DBConn.execute("UPDATE Folder SET Shared = TRUE WHERE FID = ? AND Username = ?", params)
        for row in cursor:
            FUUID = row[0]
            break
        return {"status": 200, "message": "Folder shared successfully.", "FUUID": FUUID}


@router.post("/folder/unshare", tags=["users"])
async def folderUnshare(
        folder: FolderShareInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = [folder.FolderID, session_info[1].username]
        DBConn.execute("UPDATE Folder SET Shared = FALSE WHERE FID = ? AND Username = ?", params)
        return {"status": 200, "message": "Folder unshared successfully."}


@router.post("/folder/join", tags=["users"])
async def folderJoin(
        folder: FolderJoinInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    param = list()
    param.append(folder.FUUID)
    fid = 0
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT FID, Shared FROM Folder WHERE FUUID = ?", param)
        flag = 0
        for row in cursor:
            fid = row[0]
            flag = row[1]
            break
        if flag == 0:
            return {"status": 203, "message": "Failed to join folder, this folder is not shared or not exist."}
        else:
            params = list()
            params.append(session_info[1].username)
            params.append(fid)
            cursor = DBConn.execute("SELECT Username FROM Folder WHERE Username = ? AND FID = ?", params)
            for row in cursor:
                if row[0] == session_info[1].username:
                    return {"status": 202, "message": "Failed to join folder, you are the owner of this folder."}

            params = list()
            params.append(session_info[1].userID)
            params.append(fid)
            cursor2 = DBConn.execute("SELECT UID FROM User_Folder WHERE UID = ? AND FID = ?", params)
            for row in cursor2:
                if row[0] == session_info[1].userID:
                    return {"status": 201, "message": "Failed to join folder, you are already in the list."}

            DBConn.execute("INSERT INTO User_Folder(UID, FID) VALUES (?, ?)", params)
            return {"status": 200, "message": "Folder joined successfully."}


@router.post("/folder/memberlist", tags=["users"])
async def folderMemberlist(
        folder: FolderShareInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = list()
    params.append(session_info[1].username)
    params.append(folder.FolderID)
    member_list = list()
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT FID, Shared FROM Folder WHERE Username = ? AND FID = ?", params)
        fid = 0
        shared = False
        for row in cursor:
            fid = row[0]
            shared = row[1]
            break
        if fid != folder.FolderID:
            return {"status": 202, "message": "Failed to get member list.", "sharedUserList": member_list}
        else:
            param = list()
            param.append(fid)
            members = DBConn.execute("SELECT Username FROM User_Folder, User WHERE User_Folder.UID =  User.UID AND FID = ?", param)
            for member in members:
                member_list.append(member[0])
            if shared is True:
                return {"status": 200, "message": "Folder member shown successfully.", "sharedUserList": member_list}
            else:
                return {"status": 201, "message": "Folder member shown successfully, however this folder is currently not shared.", "sharedUserList": member_list}


# 待测试
@router.post("/folder/deletemember", tags=["users"])
async def folderDeleteMember(
        folder: FolderInfo,
        member: FolderSharedMemberInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = list()
    params.append(session_info[1].username)
    params.append(folder.FolderID)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT FID FROM Folder WHERE Username = ? AND FID = ?", params)
        flag = False
        for row in cursor:
            flag = True
            break
        if flag == False:
            return {"status": 202, "message": "Failed to delete member from list, not the owner.", "deleteResult": False}
        else:
            fid = 0
            uid = 0
            for row in cursor:
                fid = row[0]
                break
            param = list()
            param.append(member.UserName)
            UserID = DBConn.execute("SELECT UID FROM User WHERE Username = ?", param)
            for ID in UserID:
                uid = ID[0]
                break
            params_uid_fid = list()
            params_uid_fid.append(fid)
            params_uid_fid.append(uid)
            member = DBConn.execute("SELECT UID FROM User_Folder WHERE FID = ? AND UID = ?", params_uid_fid)
            flag2 = False
            for row in member:
                flag2 = True
                break
            if flag2:
                DBConn.execute("DELETE FROM User_Folder WHERE FID = ? AND UID = ?", params_uid_fid)
                return {"status": 200, "message": "Folder member delete successfully.", "deleteResult": True}
            else:
                return {"status": 202, "message": "Fail to delete folder member, not a real member.", "deleteResult": False}

