# -*- coding: UTF-8 -*-
from typing import Tuple, Optional, Any, List, Dict

from pydantic import BaseModel
from fastapi import Depends, Response, HTTPException, APIRouter, Body, File, UploadFile, Form, BackgroundTasks

from fastapi_sessions import SessionCookie, SessionInfo
from fastapi_sessions.backends import InMemoryBackend
from starlette.responses import FileResponse

import sqlite3, time, jieba, os, traceback, requests, asyncio, xmltodict
import config, auth, folder, utils

router = APIRouter()


class PaperInfo(BaseModel):
    PaperID: int


class PaperMoveInfo(BaseModel):
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


class PaperNoteInfo(BaseModel):
    PaperID: int
    Note: str


class PaperDownloadInfo(BaseModel):
    PaperID: int
    Version: int


class PaperUploadInfo(BaseModel):
    PaperID: int


class PaperQueryInfo(BaseModel):
    keywords: Dict[str, str]


class PaperFuzzyQueryInfo(BaseModel):
    keywords: str


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


async def PaperRevisionDelete_(
        PID: int,
        Version: int
) -> bool:
    params = (PID, Version)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        # Step 1: Find Path of Paper Revision and delete them
        cursor = DBConn.execute("SELECT Path FROM Paper_Revision WHERE PID = ? AND Version = ?", params)
        for row in cursor:
            paperPath = row[0]
            os.remove(paperPath)

        # Step 2: Delete Paper Revision Record in DB
        cursor = DBConn.execute("DELETE FROM Paper_Revision WHERE PID = ? AND Version = ?", params)
        if cursor.rowcount == 0: return False

    return True


async def PaperUpload_(
        file: UploadFile,
        username: str
):
    SingleUserFileCountLimit = 0
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT Value FROM Setting WHERE Name = 'SingleUserFileCountLimit'")
        for row in cursor:
            SingleUserFileCountLimit = int(row[0])
            break
    SUFileCount = 0
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = (username, )
        cursor = DBConn.execute("SELECT COUNT(*) FROM Folder, Paper, Paper_Revision WHERE Username = ? AND Folder.FID = Paper.FID AND Paper.PID = Paper_Revision.PID", params)
        for row in cursor:
            SUFileCount = row[0]
            break
    if SUFileCount > SingleUserFileCountLimit:
        return {"status": 401, "message": "Uploaded file reached Single User File Count Limit."}

    FileSize = 0
    with sqlite3.connect(config.DB_PATH) as DBConn:
        cursor = DBConn.execute("SELECT Value FROM Setting WHERE Name = 'FileSize'")
        for row in cursor:
            FileSize = int(row[0]) * 1048576
            break
    res = await file.read()
    if len(res) > FileSize:
        return {"status": 402, "message": "Uploaded illegal file, filesize reached its maximium limit."}
    fileSuffix = file.filename.split('.')[-1]
    if fileSuffix not in ['pdf', 'docx', 'pptx', 'xlsx']:
        return {"status": 403, "message": "Uploaded illegal file, allowed suffix: pdf, docx, pptx, xlsx."}
    fileUploadPath = config.UPLOAD_PATH + utils.getNewUUID() + "." + fileSuffix
    with open(fileUploadPath, "wb") as f:
        f.write(res)

    return {"status": 200, "fileUploadPath":fileUploadPath}

async def PaperGenMetaData_(
        PID: int,
        fileUploadPath: str
):
    files = {'file': open(fileUploadPath, 'rb')}
    r = requests.post(config.CERMINE_URL, files=files)
    id = r.text

    flag = False
    XMLResult = ""

    for i in range(60):
        par = {'id': id}
        r = requests.get('https://cermine.renjikai.com/query.php', params=par)
        if r.text != 'Error':
            flag = True
            XMLResult = r.text
            break
        await asyncio.sleep(5)

    if not flag:
        return

    dic = xmltodict.parse(XMLResult)
    try:
        journalTitle = dic['article']['front']['journal-meta']['journal-title-group']['journal-title']
    except Exception as e:
        journalTitle = ""
    try:
        articleTitle = dic['article']['front']['article-meta']['title-group']['article-title']
    except Exception as e:
        articleTitle = ""
    try:
        year = dic['article']['front']['article-meta']['pub-date']['year']
    except Exception as e:
        year = 0
    try:
        authors = ""
        for elem in dic['article']['front']['article-meta']['contrib-group']['contrib']:
            authors += elem['string-name'] + ';'
    except Exception as e:
        authors = ""
    try:
        abstract = dic['article']['front']['article-meta']['abstract']['p']
    except Exception as e:
        abstract = ""
    try:
        keywords = ""
        for elem in dic['article']['front']['article-meta']['kwd-group']['kwd']:
            keywords += elem + ';'
    except Exception as e:
        keywords = ""

    with sqlite3.connect(config.DB_PATH) as DBConn:
        if journalTitle != "":
            params = (journalTitle, PID)
            DBConn.execute("UPDATE Paper_Meta SET Conference = ? WHERE PID = ? ", params)
        if articleTitle != "":
            params = (articleTitle, PID)
            DBConn.execute("UPDATE Paper_Meta SET Title = ? WHERE PID = ? ", params)
        if year != 0:
            params = (year, PID)
            DBConn.execute("UPDATE Paper_Meta SET Year = ? WHERE PID = ? ", params)
        if authors != "":
            params = (authors, PID)
            DBConn.execute("UPDATE Paper_Meta SET Authors = ? WHERE PID = ? ", params)
        if abstract != "":
            params = (abstract, PID)
            DBConn.execute("UPDATE Paper_Meta SET Abstract = ? WHERE PID = ? ", params)
        if keywords != "":
            params = (keywords, PID)
            DBConn.execute("UPDATE Paper_Meta SET Keywords = ? WHERE PID = ? ", params)


async def JieBaCut_(
        keywords: str
):
    keywordList = jieba.lcut(keywords)
    keywordList2 = []
    for kw in keywordList:
        if kw.strip() != '':
            keywordList2.append(kw.strip())

    return keywordList2

@router.post("/paper/import", tags=["users"])
async def paperImport(
        background_tasks: BackgroundTasks,
        FolderID: int = Form(...),
        file: UploadFile = File(...),
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
    start = time.time()
    try:
        uploadResult = await PaperUpload_(file, session_data[1].username)
        if uploadResult['status'] != 200:
            return uploadResult
        fileUploadPath = uploadResult["fileUploadPath"]

        fid = list()
        fid.append(FolderID)
        with sqlite3.connect(config.DB_PATH) as DBConn:
            DBConn.execute("INSERT INTO Paper(FID, Lock) VALUES (?, FALSE)", fid)
            cursor = DBConn.execute("SELECT MAX(PID) FROM Paper") # Thread unsafe
            pid = 0
            for r in cursor:
                pid = r[0]
                break
            params = [pid, session_data[1].username, time.time(), fileUploadPath]
            DBConn.execute("INSERT INTO Paper_Revision(PID, Edit_User, Edit_Time, Version, Path) VALUES (?, ?, ?, 0, ?)", params)
            params2 = [pid, file.filename]
            DBConn.execute("INSERT INTO Paper_Meta(PID, Title) VALUES (?,?)", params2)
            background_tasks.add_task(PaperGenMetaData_, pid, fileUploadPath)
            return {"status": 200, "message": "Paper successfully imported.", 'time': time.time() - start, 'PID': pid}
    except Exception as e:
        traceback.print_exc()
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
        cursor = DBConn.execute("UPDATE Paper SET FID = ? WHERE PID = ?", params)
        if cursor.rowcount == 1:
            return {"status": 200, "message": "Paper moved successfully.", "flag": True}
        else:
            return {"status": 202, "message": "Fail to move paper.", "flag": False}


@router.post("/paper/modifymetadata", tags=["users"])
async def paperModifyMetadata(
        paper_meta: PaperMetaInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = [paper_meta.Title, paper_meta.Authors, paper_meta.Conference, paper_meta.Abstract,
                  paper_meta.Keywords, paper_meta.Year, paper_meta.PaperID]
        DBConn.execute("UPDATE Paper_Meta SET Title = ?, Authors = ?, Conference = ?, Abstract = ?, Keywords = ?, Year = ? WHERE PID = ?", params)
        return {"status": 200, "message": "Paper Meta updated successfully.", "pid": paper_meta.PaperID}


@router.post("/paper/getmetadata", tags=["users"])
async def paperGetMetadata(
        paper_info: PaperInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        param = [paper_info.PaperID]
        cursor = DBConn.execute("SELECT Title, Authors, Conference, Abstract, Keywords, Year FROM Paper_Meta WHERE PID = ?", param)
        meta = dict()
        for row in cursor:
            meta['Title'] = row[0]
            meta['Authors'] = row[1]
            meta['Conference'] = row[2]
            meta['Abstract'] = row[3]
            meta['Keywords'] = row[4]
            meta['Year'] = row[5]
            break
        params = [paper_info.PaperID]
        version = DBConn.execute("SELECT MAX(Version) FROM Paper_Revision WHERE PID = ?", params)
        for row in version:
            params.append(row[0])
            break
        cursor = DBConn.execute("SELECT PID, Path FROM Paper_Revision WHERE PID = ? AND Version = ?", params)
        pid = 0
        path = ""
        add_time = str()
        for r in cursor:
            pid = r[0]
            path = r[1]
            break
        add_time_cursor = DBConn.execute("SELECT Edit_Time FROM Paper_Revision WHERE PID = ? AND Version = 0", param)
        for r in add_time_cursor:
            timeArray = time.localtime(r[0])
            add_time = str(time.strftime("%Y-%m-%d", timeArray))
            break

        if pid == paper_info.PaperID:
            tmp = path.split('.')
            meta['Type'] = tmp[-1]
            meta['AddTime'] = add_time
            meta['PID'] = pid
            return {"status": 200, "message": "Paper Meta updated successfully.", "meta": meta}
        return {"status": 202, "message": "Something is wrong"}


@router.post("/paper/getnote", tags=["users"])
async def paperGetNote(
        paper_info: PaperInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        note = str()
        params = [paper_info.PaperID]
        cursor = DBConn.execute("SELECT Note FROM Paper_Meta WHERE PID = ?", params)
        for row in cursor:
            note = row[0]
        return {"status": 200, "message": "Paper note got successfully.", "note": note}


@router.post("/paper/modifynote", tags=["users"])
async def paperModifyNote(
        paper_note: PaperNoteInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
    with sqlite3.connect(config.DB_PATH) as DBConn:
        params = [paper_note.Note, paper_note.PaperID]
        DBConn.execute("UPDATE Paper_Meta SET Note = ? WHERE PID = ?", params)
        return {"status": 200, "message": "Paper note updated successfully.", "pid": paper_note.PaperID}


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


@router.post("/paper/query", tags=["users"])
async def paperQuery(
        PQI: PaperQueryInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
    dic = PQI.keywords

    PIDS = []
    with sqlite3.connect(config.DB_PATH) as DBConn:
        SQL = f"SELECT Paper.PID FROM Paper_Meta, Paper, Folder WHERE Folder.FID = Paper.FID And Paper.PID = Paper_Meta.PID AND Username = {session_data[1].username} AND ("
        for qw in dic.keys():
            for kw in await JieBaCut_(dic[qw]):
                SQL += f" '{qw}' LIKE '%{kw}%' OR "
        SQL += "0 )"
        cursor = DBConn.execute(SQL)
        for row in cursor:
            PIDS.append(row[0])

    return {"status": 200, "message": "Paper queried successfully.", "pids": PIDS}


@router.post("/paper/fuzzyquery", tags=["users"])
async def papeFuzzyQuery(
        PFQI: PaperFuzzyQueryInfo,
        session_data: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_data)
    keywords = PFQI.keywords
    query_type = ['Title', 'Authors', 'Conference', 'Keywords', 'Year']
    keywordList = jieba.lcut(keywords)
    keywordList2 = []
    for kw in keywordList:
        if kw.strip() != '':
            keywordList2.append(kw.strip())

    if len(keywordList2) == 0:
        return {"status": 200, "message": "Paper queried successfully.", "pids": {}}

    PIDS = []
    with sqlite3.connect(config.DB_PATH) as DBConn:
        SQL = f"SELECT Paper.PID FROM Paper_Meta, Paper, Folder WHERE Folder.FID = Paper.FID And Paper.PID = Paper_Meta.PID AND Username = {session_data[1].username} AND ("
        for qw in query_type:
            for kw in keywordList2:
                SQL += f" {qw} LIKE '%{kw}%' OR "
        SQL += "0 )"
        cursor = DBConn.execute(SQL)
        print(SQL)
        for row in cursor:
            PIDS.append(row[0])

    return {"status": 200, "message": "Paper queried successfully.", "pids": PIDS}


@router.post("/paper/lock", tags=["users"])
async def paperLock(
        paper: PaperInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = [paper.PaperID]
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
    params = [paper.PaperID]
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
            return {"status": 200, "message": "Paper download successfully.", "address": config.SITE_PATH + path}
        else:
            return {"status": 202, "message": "Fail to download paper."}


@router.post("/paper/downloadlatest", tags=["users"])
async def paperDownloadLatest(
        paper: PaperInfo,
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    params = list()
    params.append(paper.PaperID)

    with sqlite3.connect(config.DB_PATH) as DBConn:
        version = DBConn.execute("SELECT MAX(Version) FROM Paper_Revision WHERE PID = ?", params)
        for row in version:
            params.append(row[0])
            break
        cursor = DBConn.execute("SELECT PID, Path FROM Paper_Revision WHERE PID = ? AND Version = ?", params)
        pid = 0
        path = ""
        for r in cursor:
            pid = r[0]
            path = r[1]
            break
        return {"status": 200, "message": "Paper download successfully.", "address": config.SITE_PATH + path}


# 此函数待讨论，我的意思是把现有版本同步到云端的操作。本函数还未加入接口说明中。
@router.post("/paper/upload", tags=["users"])
async def paperUpload(
        PaperID: int = Form(...),
        file: UploadFile = File(...),
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    try:
        FileRevisionLimit = 0
        with sqlite3.connect(config.DB_PATH) as DBConn:
            cursor = DBConn.execute("SELECT Value FROM Setting WHERE Name = 'FileRevisionLimit'")
            for row in cursor:
                FileRevisionLimit = row[0]
                break
        FRUsage = 0
        with sqlite3.connect(config.DB_PATH) as DBConn:
            params = (PaperID,)
            cursor = DBConn.execute("SELECT COUNT(*) FROM Paper_Revision WHERE Paper.PID = ? ", params)
            for row in cursor:
                FRUsage = row[0]
                break
        if FRUsage > FileRevisionLimit:
            minVer = -1
            with sqlite3.connect(config.DB_PATH) as DBConn:
                params = (PaperID,)
                cursor = DBConn.execute("SELECT MIN(Version) FROM Paper_Revision WHERE Paper.PID = ? ", params)
                for row in cursor:
                    minVer = row[0]
                    break
                if minVer != -1:
                    await PaperRevisionDelete_(PaperID, minVer)

        uploadResult = await PaperUpload_(file, session_info[1].username)
        if uploadResult['status'] != 200:
            return uploadResult
        fileUploadPath = uploadResult["fileUploadPath"]

        with sqlite3.connect(config.DB_PATH) as DBConn:
            params = list()
            version = 0
            params.append(PaperID)
            cursor_version = DBConn.execute("SELECT MAX(Version) FROM Paper_Revision WHERE PID = ?", params)
            for r in cursor_version:
                version = r[0]
                break
            params.append(session_info[1].username)
            params.append(time.time())
            params.append(version+1)
            params.append(fileUploadPath)
            params.append(PaperID)
            DBConn.execute("INSERT INTO Paper_Revision SET Edit_User = ?, Edit_Time = ?, Version = ?, Path = ? WHERE PID = ?", params)
            return {"status": 200, "message": "Paper upload successfully.",
                    "info": {"PID": PaperID, "editUser": params[0], "editTime": params[1], "version": params[2]}}
    except Exception as e:
        traceback.print_exc()
        return {"status": 400, "message": str(e), "PID": PaperID}


@router.post("/paper/list", tags=["users"])
async def paperList(
        paper: PaperInfo,
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


@router.get("/paper/all", tags=["users"])
async def paperAll(
        session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    await auth.checkLogin(session_info)
    param = [session_info[1].username]
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
