from fastapi import FastAPI

app = FastAPI()

@app.get('/')
def index():
    return {'message': 'You have successfully created FastAPI service!'}