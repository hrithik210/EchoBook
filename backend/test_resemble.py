from json import load
from resemble import Resemble
import os
from dotenv import load_dotenv

load_dotenv()


Resemble.api_key(os.getenv("RESEMBLE_API"))

# Get your default Resemble project.
project_uuid = Resemble.v2.projects.all(1, 10)['items'][0]['uuid']

# Get your Voice uuid. In this example, we'll obtain the first.
voice_uuid = Resemble.v2.voices.all(1, 10)['items'][0]['uuid']

print("🗣️  Generating test clip...")
body = 'Hello, this is your first audiobook test.'
response = Resemble.v2.clips.create_sync(project_uuid,
                                         voice_uuid,
                                         body,
                                         title=None,
                                         sample_rate=None,
                                         output_format='wav',
                                         precision=None,
                                         include_timestamps=None,
                                         is_archived=None,
                                         raw=None)
if response['success']:
    audio_url = response['item']['audio_src']
    print(f"✅ Success! Download audio here: {audio_url}")
else:
    print(f"❌ Failed: {response}")