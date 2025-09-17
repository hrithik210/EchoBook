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
    
    audio_data = requests.get(audio_data).content
    
    with open(output_path, 'wb') as f:
        f.write(audio_data)
    
    print(f"saved to {output_path}")