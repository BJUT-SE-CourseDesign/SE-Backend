from fastapi import FastAPI
import auth
import paper
import folder

app = FastAPI()

app.include_router(auth.router)
app.include_router(paper.router)
app.include_router(folder.router)

@app.get('/')
def index():
    return {'message': 'You have successfully created FastAPI service!'}