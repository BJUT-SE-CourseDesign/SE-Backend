from typing import Tuple, Optional, Any
from fastapi import FastAPI
from fastapi_sessions import SessionInfo
from fastapi import Depends, Response, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

import auth, config
import paper
import folder

from admin import settings
from admin import folder as fd
from admin import user

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://127.0.0.1:8080',
        'http://localhost:8080',
    ],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET_KEY,
    same_site="None",
    https_only=True
)

app.include_router(auth.router)
app.include_router(paper.router)
app.include_router(folder.router)
app.include_router(settings.router)
app.include_router(fd.router)
app.include_router(user.router)


@app.get('/')
def index(
    session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info:
        return {"status": 200, 'message': 'Welcome to SE Backend!'}
    else:
        return {"status": 403, 'message': "Not logged in! We don't welcome you!"}
