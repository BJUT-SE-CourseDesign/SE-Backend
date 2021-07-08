from typing import Tuple, Optional, Any
from fastapi import FastAPI
from fastapi_sessions import SessionInfo
from fastapi import Depends, Response, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware

import auth
import paper
import folder

app = FastAPI()

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
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


@app.get('/')
def index(
    session_info: Optional[SessionInfo] = Depends(auth.curSession)
):
    if session_info:
        return {"status": 200, 'message': 'Welcome to SE Backend!'}
    else:
        return {"status": 403, 'message': "Not logged in! We don't welcome you!"}
