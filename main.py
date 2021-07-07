from typing import Tuple, Optional, Any
from fastapi import FastAPI
from fastapi_sessions import SessionInfo
from fastapi import Depends, Response, HTTPException, APIRouter

import auth
import paper
import folder

app = FastAPI()

app.include_router(auth.router)
app.include_router(paper.router)
app.include_router(folder.router)


@app.get('/')
def index(
    session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info:
        return {"status": 200, 'message': 'Welcome to SE Backend!'}
    else:
        return {"status": 403, 'message': "Not logged in! We don't welcome you!"}
