import asyncio
import json
import os
import time
import threading
import concurrent.futures
from queue import SimpleQueue
from fastapi import WebSocket
from google.cloud import speech_v1p1beta1 as speech
from dotenv import load_dotenv
from app.openai_service import generate_openai_response_stream
from app.audio_utils import text_to_speech

load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

speech_client = speech.SpeechClient()

async def websocket_stt_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(time.time()).replace('.', '')
    print(f"🔗 STT connection: {session_id}")

    streaming_config = speech.StreamingRecognitionConfig(
        config=speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=48000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="default",
            use_enhanced=True,
            speech_contexts=[
                speech.SpeechContext(phrases=["OpenAI", "ChatGPT", "JavaScript", "React", "WebRTC"])
            ],
        ),
        interim_results=True,
        single_utterance=False
    )

    requests = asyncio.Queue()

    async def receive_audio():
        try:
            while True:
                data = await websocket.receive_bytes()
                await requests.put(speech.StreamingRecognizeRequest(audio_content=data))
        except Exception as e:
            print("Receive error", e)
            await requests.put(None)  # Signal end of stream

    async def process_stt():
        sync_queue = SimpleQueue()
        last_transcript = ""
        current_ai_task = None  
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor()

        def request_generator():
            while True:
                item = sync_queue.get()
                if item is None:
                    break
                yield item

        async def transfer_requests():
            while True:
                item = await requests.get()
                if item is None:
                    sync_queue.put(None)
                    break
                sync_queue.put(item)

        async def handle_ai_and_tts(transcript: str):
            try:
                full_response = ""
                async for partial in generate_openai_response_stream(transcript):
                    full_response += partial  # Keep building the response

                if full_response:
                    audio_bytes = text_to_speech(full_response)
                    await websocket.send_bytes(audio_bytes)  # 🎧 Send only audio
                else:
                    print("⚠️ Empty OpenAI response")
            except Exception as e:
                print("AI+TTS error:", e)


        def stt_blocking():
            nonlocal current_ai_task, last_transcript
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
                        last_transcript = ""

                        asyncio.run_coroutine_threadsafe(
                            websocket.send_text(json.dumps({"transcript": transcript, "isFinal": True})),
                            loop
                        )

                        # Cancel existing AI task
                        if current_ai_task and not current_ai_task.done():
                            current_ai_task.cancel()
                            try:
                                asyncio.run_coroutine_threadsafe(current_ai_task, loop).result()
                            except Exception as e:
                                print("Cancelled previous task:", e)

                        # Start new AI+TTS task
                        current_ai_task = asyncio.run_coroutine_threadsafe(
                            handle_ai_and_tts(transcript), loop
                        )
                    elif transcript != last_transcript:
                        last_transcript = transcript
                        print("🔄 Interim:", transcript)
                        asyncio.run_coroutine_threadsafe(
                            websocket.send_text(json.dumps({"transcript": transcript, "isFinal": False})),
                            loop
                        )
            except Exception as e:
                print("STT error:", e)
                asyncio.run_coroutine_threadsafe(
                    websocket.send_text(json.dumps({"error": str(e)})), loop
                )

        # Run producer-consumer concurrently
        transfer_task = asyncio.create_task(transfer_requests())
        stt_task = loop.run_in_executor(executor, stt_blocking)

        await transfer_task
        await stt_task

    await asyncio.gather(receive_audio(), process_stt())
