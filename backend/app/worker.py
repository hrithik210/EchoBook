import enum
import os
import re
import uuid
from pathlib import Path
from pypdf import PdfReader
from pydub import AudioSegment
from resemble import Resemble
from dotenv import load_dotenv
import requests
load_dotenv()

Resemble.api_key(os.getenv("RESEMBLE_API"))
# Get your default Resemble project.
project_uuid = Resemble.v2.projects.all(1, 10)['items'][0]['uuid']

# Get your Voice uuid. In this example, we'll obtain the first.
default_voice_uuid = Resemble.v2.voices.all(1, 10)['items'][0]['uuid']

def text_to_speech(text : str , output_path : str ,voice_uuid : str = default_voice_uuid):
    print(f"🗣️  TTS: '{text[:50]}...'")
    
    response = Resemble.v2.clips.create_sync(project_uuid,
                                             voice_uuid,
                                             body=text,
                                             title=None,
                                             output_format="wav",
                                             sample_rate=22050,
                                             precision="PCM_16")

    if not response['success']:
        raise Exception(f"response failed : {response}")
    
    audio_src = response['item']['audio_src']
    print(f"downloading audio : {audio_src}")
    
    audio_data = requests.get(audio_src).content
    
    with open(output_path, 'wb') as f:
        f.write(audio_data)
    
    print(f"saved to {output_path}")
    
def process_pdf_to_audioBook(pdf_path : str , output_dir : str , voice_uuid : str = default_voice_uuid):
    
    os.makedirs(output_dir, exist_ok=True)
    chunk_dir = Path(output_dir)/"chunks"
    os.makedirs(chunk_dir , exist_ok=True)
    
    reader = PdfReader(pdf_path)
    texts = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        
        if text.strip():
            texts.append((i+1, text))
    
    audio_files = []
    
    for page_num, text in texts:
        wav_path = chunk_dir/f"page_{page_num}.wav"
        text_to_speech(text, str(wav_path), voice_uuid, )
        audio_files.append(str(wav_path))
        
    print("combining audios")
    
    combined = AudioSegment.empty()
    
    for wav_file in audio_files:
        combined+=AudioSegment.from_wav(wav_file)
    
    mp3_path = Path(output_dir)/"audiobook.mp3"
    combined.export(str(mp3_path),format="mp3")
    print(f"🎉 Final audiobook saved: {mp3_path}")
    
    return str(mp3_path)

# Define pdf_path at module level so it can be imported
pdf_path = "/Users/hrithik/audoBook-generator/test.pdf"   # replace with your PDF path

if __name__ == "__main__":
    output_dir = "output"
    process_pdf_to_audioBook(pdf_path, output_dir)
