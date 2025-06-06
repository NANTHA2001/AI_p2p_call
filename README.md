#AI_p2p_call

A real-time voice-based conversational AI system that lets users speak naturally and get intelligent voice responses—powered by OpenAI, Google Speech-to-Text (STT), and gTTS.

🎯 Overview
This project enables live voice interaction with OpenAI's language model. The user speaks into their mic, and the system:

1.Captures and encodes the audio in real-time.

2.Transcribes it using Google Speech-to-Text.

3.Sends the transcription to OpenAI for generating a response.

4.Converts the AI's response back into speech using gTTS (Google Text-to-Speech).

5.Streams the audio response back to the user for a seamless conversation.


🛠️ How It Works
📦 Frontend (React/JavaScript)
1.Captures microphone audio in real-time.

2.Converts the audio to 16-bit PCM format.

3.Sends audio frames to the backend over a WebSocket.

🔁 Backend (FastAPI + WebSocket)
The websocket_stt.py module receives raw audio frames from the frontend.

1.Google STT API transcribes the audio into text.

2.The transcribed text is sent to OpenAI GPT-4 to generate a natural language response.

3.The generated text is converted to speech using gTTS (Google Text-to-Speech).

4.The voice response is streamed back to the client.



🗣️ Use Case Example
User speaks: "What’s the weather like in New York today?"

Audio is streamed → transcribed to text → processed by GPT-4 → replied with:
"Today in New York, it’s sunny with a high of 26°C."

Response is converted into audio → streamed back to the user.