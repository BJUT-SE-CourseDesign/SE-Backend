from typing import Tuple, Optional, Any
from fastapi import FastAPI
from fastapi_sessions import SessionInfo
from fastapi import Depends, Response, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware

import auth
import paper
import folder

from admin import settings
from admin import folder as fd
from admin import user

app = FastAPI()

origins = [
    "http://127.0.0.1",
    "http://127.0.0.1:8080",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
