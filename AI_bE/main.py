import os
from fastapi import FastAPI, WebSocket
from app.websocket_stt import websocket_stt_endpoint

app = FastAPI()

@app.websocket("/ws-stt")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_stt_endpoint(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
