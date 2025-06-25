import asyncio
import json
import os
import time
import threading
import concurrent.futures
from queue import SimpleQueue
from fastapi import WebSocket
from dotenv import load_dotenv
from app.audio_utils import text_to_speech
from app.knowledge_openai import generate_openai_response_stream

from google.cloud import speech_v1p1beta1 as speech
from google.oauth2 import service_account

load_dotenv()

audio_buffer_size = 2048

async def websocket_stt_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
    except Exception as e:
        print("⚠️ WebSocket accept error:", e)
        return

    session_id = str(time.time()).replace('.', '')
    print(f"🔗 STT connection: {session_id}")

    stop_event = threading.Event()
    audio_queue = asyncio.Queue()
    sync_queue = SimpleQueue()
    transcript_queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor()

    # ✅ Load credentials from env (Railway-compatible)
    credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_json:
        raise RuntimeError("Missing GOOGLE_APPLICATION_CREDENTIALS_JSON env variable")
    credentials_info = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(credentials_info)

    # ✅ Use credentials to create SpeechClient
    speech_client = speech.SpeechClient(credentials=credentials)

    streaming_config = speech.StreamingRecognitionConfig(
        config=speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=48000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            diarization_speaker_count=2,
            model="default",
            use_enhanced=True,
            speech_contexts=[
                speech.SpeechContext(
                    phrases=["Bigthinkcode", "Hey Nova", "Nova", "Okay Nova", "Hello Nova"],
                    boost=25.0  # you can also try 15.0 if too sensitive
                ),
                speech.SpeechContext(phrases=["OpenAI", "ChatGPT", "JavaScript", "React", "WebRTC"])
            ],
        ),
        interim_results=True,
        single_utterance=False
    )

    def request_generator():
        while not stop_event.is_set():
            item = sync_queue.get()
            if item is None:
                break
            yield item

    async def receive_audio():
        buffer = b''
        last_send = time.time()
        try:
            while not stop_event.is_set():
                data = await websocket.receive_bytes()
                buffer += data
                if time.time() - last_send >= 0.2:
                    sync_queue.put(speech.StreamingRecognizeRequest(audio_content=buffer))
                    buffer = b''
                    last_send = time.time()
        except Exception as e:
            print("🔴 Receive error:", e)
            sync_queue.put(None)
            stop_event.set()

    async def send_silence_fill():
        SILENCE_CHUNK = b'\x00' * 9600  # 100ms of silence @ 48kHz mono 16-bit
        while not stop_event.is_set():
            await asyncio.sleep(0.1)  # Send every 100ms
            sync_queue.put(speech.StreamingRecognizeRequest(audio_content=SILENCE_CHUNK))


    def stt_blocking():
        last_transcript = ""
        try:
            for response in speech_client.streaming_recognize(streaming_config, request_generator()):
                if not response.results:
                    continue
                result = response.results[0]
                if not result.alternatives:
                    continue
                transcript = result.alternatives[0].transcript.strip()

                if transcript and result.is_final:
                    print("✅ Final:", transcript)
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_text(json.dumps({"transcript": transcript, "isFinal": True})), loop
                    )
                    asyncio.run_coroutine_threadsafe(transcript_queue.put(transcript), loop)
                elif transcript != last_transcript:
                    last_transcript = transcript
                    print("🔄 Interim:", transcript)
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_text(json.dumps({"transcript": transcript, "isFinal": False})), loop
                    )
        except Exception as e:
            print("🛑 STT error:", e)
            asyncio.run_coroutine_threadsafe(
                websocket.send_text(json.dumps({"error": str(e)})), loop
            )

    async def handle_ai_worker():
        current_task = None

        while not stop_event.is_set():
            transcript = await transcript_queue.get()

            # Cancel previous task if still running
            if current_task and not current_task.done():
                current_task.cancel()
                print("⛔ Previous AI response interrupted")

            async def process_transcript(text: str):
                try:
                    print("🔍 Fetching OpenAI response for:", text)
                    text_stream = generate_openai_response_stream(text)

                    full_response = ""
                    async for chunk in text_stream:
                        full_response += chunk

                    if not full_response.strip():
                        raise ValueError("Empty response from OpenAI")

                    audio_bytes = text_to_speech(full_response)
                    await websocket.send_bytes(audio_bytes)

                except asyncio.CancelledError:
                    print("🛑 AI task was cancelled")
                except asyncio.TimeoutError:
                    fallback = "Sorry, I didn't catch that. Could you rephrase or try another question?"
                    audio_bytes = text_to_speech(fallback)
                    await websocket.send_bytes(audio_bytes)
                except Exception as e:
                    print("AI+TTS error:", e)
                    fallback = "I'm not sure how to respond to that. Could you try something else?"
                    audio_bytes = text_to_speech(fallback)
                    await websocket.send_bytes(audio_bytes)

            current_task = asyncio.create_task(process_transcript(transcript))


    async def watchdog():
        await asyncio.sleep(290)
        stop_event.set()
        sync_queue.put(None)

    tasks = [
        asyncio.create_task(receive_audio()),
        asyncio.create_task(send_silence_fill()),
        asyncio.create_task(handle_ai_worker()),
        asyncio.create_task(watchdog())
    ]
    loop.run_in_executor(executor, stt_blocking)

    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in tasks:
        task.cancel()

    print("❌ WebSocket session ended")
