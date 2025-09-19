import os
from tkinter import RAISED
import uuid
from pathlib import Path
from typing import Dict
from fastapi import FastAPI,UploadFile,File,Form,HTTPException, status
from fastapi.responses import FileResponse
import shutil
from concurrent.futures import ThreadPoolExecutor

from resemble import Resemble
from app.worker import default_voice_uuid, pdf_path, process_pdf_to_audioBook


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
    
    # Save uploaded file
    uploaded_pdf_path = job_dir / file.filename
    with open(uploaded_pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    #registering job
    jobs[job_id] = {
        "status" : "processing",
        "output_path" : None,
        "voice_uuid" : voice_uuid
    }
    
    #start background processing
    executor.submit(
        background_process,
        str(uploaded_pdf_path),
        str(job_dir),
        voice_uuid,
        job_id
    )
    
    return {
        "message"  : "processing your req, please wait for a bit",
        "job_id" : job_id,
        "voice_uuid" : voice_uuid
    }

def background_process(pdf_path:str , output_dir : str, voice_uuid , job_id : str):
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
        
@app.get("/status/{job_id}")
async def getStatus(job_id:str):
    job = jobs.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    
    return job

@app.get("/download/{job_id}")
async def download_audio(job_id : str):
    
    job  = jobs[job_id]
    
    if not job:
        raise HTTPException(status_code=404 , detail="job not found")
    
    if job['status'] != "done":
        raise HTTPException(status_code=400 , detail="job is still in processing")
    
    mp3_path = job['output_path']
    
    if not os.path.exists(mp3_path):
        raise HTTPException(status_code=404 , detail="file missing")
    
    return FileResponse(mp3_path, filename="audio_book.mp3" , status_code=200)

@app.get("/voices")
def list_voices():
    from app.worker import project_uuid
    from resemble import Resemble

    voices = Resemble.v2.voices.all(1, 20)
    return {"voices": voices['items']}



def createEmptyVoice(project_uuid : str , name : str):
    response = Resemble.v2.voices.create(
        project_uuid,
        name=name,
        voice_type="rapid"
    )

    if not response['success']:
        raise HTTPException(status_code=400 , detail=f"failed to create voice : {response}")
    voice_uuid = response['item']['uuid']
    print(f"voice container created successfully  :{voice_uuid}")
    
    return voice_uuid

@app.post("/clone-voice")
async def cloneVoice(name : str = Form(...) , sample : UploadFile = File(...)):
    '''upload a voice sample here it clones the voice and returns voice uuid'''
    
    if not sample.filename.endswith("wav", "mp3", "ogg"):
        raise HTTPException(status=400 , detail="invalid upload voice format")
    
    try:
        response = Resemble.v2
    