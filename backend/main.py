from app.main import app
import uvicorn

if __name__=="main":
    uvicorn.run(app, port=8000,  reload=True)
