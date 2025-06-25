import edge_tts
import asyncio
import tempfile

async def text_to_speech(text: str) -> bytes:
    async with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        await edge_tts.Communicate(text, "en-US-JennyNeural").save(tmp.name)
        tmp.seek(0)
        audio = tmp.read()
    return audio
