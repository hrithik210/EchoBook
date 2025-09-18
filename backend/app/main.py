from email import message
import os
import uuid
from pathlib import Path
from typing import Dict
from fastapi import FastAPI,UploadFile,File,Form,HTTPException
from fastapi.responses import FileResponse
import shutil
from concurrent.futures import ThreadPoolExecutor
from .worker import default_voice_uuid, pdf_path, process_pdf_to_audioBook


app = FastAPI(title="EchoBook_backend")

jobs: Dict = {}
JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(exist_ok=True)

#background working pool
executor = ThreadPoolExecutor()

@app.post("/upload")
async def upload(file : UploadFile = File(...) , voice_uuid : str = Form(default_voice_uuid) ):
    if not file.filename.endswith("pdf"):
        raise HTTPException(status_code=400 , detail="we only support .pdf for now")
    
    job_id = str(uuid.uuid4())
    job_dir = JOBS_DIR/job_id
    job_dir.mkdir()
    
    #registering job
    jobs[job_id] = {
        "status" : "processing",
        "output_path" : None,
        "voice_uuid" : voice_uuid
    }
    
    #start background processing
    executor.submit(
        backgroud_process,
        str(pdf_path),
        str(job_dir),
        voice_uuid,
        job_id
    )
    
    return {
        "message"  : "processing your req, please wait for a bit",
        "job_id" : job_id,
        "voice_uuid" : voice_uuid
    }

async def backgroud_process(pdf_path:str , output_dir : str, voice_uuid , job_id : str):
    try:
        mp3_path = process_pdf_to_audioBook(pdf_path, output_dir , voice_uuid)
        jobs[job_id]= {
            "status" : "done",
            "output_path" : mp3_path
        }
    except Exception as e:
        jobs[job_id] = {
            "status" : "failed",
            "error" : f"{e}"
        }
        print(f"❌ Job {job_id} failed: {e}")
        
    