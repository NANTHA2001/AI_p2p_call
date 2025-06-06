from fastapi import FastAPI, WebSocket
from app.websocket_stt import websocket_stt_endpoint


app = FastAPI()

@app.websocket("/ws-stt")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_stt_endpoint(websocket)