import os
import uuid
from pathlib import Path
from typing import Dict
from fastapi import FastAPI,UploadFile,File,Form,HTTPException, status
from fastapi.responses import FileResponse
import shutil
from concurrent.futures import ThreadPoolExecutor
from pydub import AudioSegment
from resemble import Resemble
from app.worker import default_voice_uuid, pdf_path, process_pdf_to_audioBook, project_uuid
from tempfile import NamedTemporaryFile

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


def convert_to_wav_if_needed(input_path: str) -> str:
    """
    If file is not .wav, convert it to 16-bit PCM WAV at 22050 Hz.
    Returns path to WAV file (original or converted).
    """
    if input_path.lower().endswith(".wav"):
        print("✅ File is already .wav")
        return input_path

    # Convert using pydub
    print(f"🔄 Converting {input_path} to .wav...")
    audio = AudioSegment.from_file(input_path)

    # Export as 16-bit PCM WAV at 22050 Hz (Resemble-friendly)
    wav_path = input_path.rsplit(".", 1)[0] + ".wav"
    audio.export(wav_path, format="wav", parameters=["-ar", "22050", "-ac", "1", "-sample_fmt", "s16"])

    print(f"✅ Converted and saved to: {wav_path}")
    return wav_path

def createEmptyVoice(project_uuid: str, name : str):
    response = Resemble.v2.voices.create(
        name,
        consent="I agree to the terms of service",
        voice_type="rapid"
    )

    if not response['success']:
        raise HTTPException(status_code=400 , detail=f"failed to create voice : {response}")
    voice_uuid = response['item']['uuid']
    print(f"voice container created successfully  :{voice_uuid}")
    
    return voice_uuid

def upload_Recording_to_voice(project_uuid : str, name: str , audio_file_Path : str , voice_uuid : str):
    response = Resemble.v2.recordings.create(
        project_uuid,
        voice_uuid=voice_uuid,
        file=audio_file_Path,
        name=name,
    )
    if not response['success']:
        raise Exception(f"Failed to upload recording: {response}")
    recording_uuid = response['item']['uuid']
    print(f"✅ Recording uploaded: {recording_uuid}")
    return recording_uuid

def start_voice_training(project_uuid: str , voice_uuid : str):
    response = Resemble.v2.voices.build(
        project_uuid,
        uuid=voice_uuid
    )
    if not response['success']:
        raise Exception(f"Failed to start training: {response}")

    print(f"✅ Training started for voice: {voice_uuid}")
    
    
def clone_voice_from_file(project_uuid,voice_name :str , audio_path: str):
    
    wav_path = convert_to_wav_if_needed(audio_path)
    #step:1 create empty file
    voice_uuid = createEmptyVoice(project_uuid, name=voice_name)
    
    #step:2 upload the same file 3 time
    for i in range(3):
        upload_Recording_to_voice(
            project_uuid,
            name=voice_name,
            audio_file_Path=wav_path,
            voice_uuid=voice_uuid
        )
    #step3 : building voice
    start_voice_training(project_uuid, voice_uuid=voice_uuid)
    
    return voice_uuid



@app.post("/clone-voice")
async def cloneVoice(name : str = Form(...) , sample : UploadFile = File(...)):
    '''upload a voice sample here it clones the voice and returns voice uuid'''
    
    if not sample.filename.endswith((".wav", ".mp3", ".ogg")):
        raise HTTPException(status=400 , detail="invalid upload voice format")
    
    # Save uploaded file temporarily
    with NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        shutil.copyfileobj(sample.file, tmp)
        tmp_path = tmp.name
    

    
    try:
        voice_uuid = clone_voice_from_file(project_uuid=project_uuid,voice_name=name , audio_path=tmp_path )
    except Exception as e:
        raise HTTPException(500, f"Voice cloning failed: {str(e)}")
    finally:
        os.unlink(tmp_path)
    
    return {
        "message": "Voice cloning started. Training may take 30-60 seconds.",
        "voice_uuid": voice_uuid,
        "name": name,
        "status": "training"
    }