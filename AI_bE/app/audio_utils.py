from gtts import gTTS
import io

def text_to_speech(text: str) -> bytes:
    tts = gTTS(text=text, lang='en')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp.read()