from fastapi import FastAPI
import auth

app = FastAPI()

app.include_router(auth.router)

@app.get('/')
def index():
    return {'message': 'You have successfully created FastAPI service!'}