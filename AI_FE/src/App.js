import React, { useState, useRef, useEffect } from 'react';
import './App.css';

function RobotProfile({ isSpeaking, isListening, label }) {
  return (
    <div className="profile-container">
      <div className={`robot ${isSpeaking ? 'speaking' : ''} ${isListening ? 'listening' : ''}`}>
        <svg viewBox="0 0 64 64" width="100" height="100">
          <g fill="none" stroke="#2196f3" strokeWidth="2">
            <circle cx="32" cy="32" r="30" fill="#111" stroke="#2196f3" />
            <circle cx="22" cy="24" r="4" fill="#4caf50" />
            <circle cx="42" cy="24" r="4" fill="#4caf50" />
            <path d="M22 40 q10 10 20 0" stroke="#eee" strokeWidth="3" />
            <rect x="28" y="8" width="8" height="8" fill="#2196f3" rx="2" />
          </g>
        </svg>
        <div className="status-ring" />
      </div>
      <div className="label">{label}</div>
    </div>
  );
}

export default function App() {
  const [isRecording, setIsRecording] = useState(false);
  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const workletNodeRef = useRef(null);
  const sourceRef = useRef(null);
  const currentAudioSourceRef = useRef(null);

  const [volume, setVolume] = useState(0);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [aiThinking, setAiThinking] = useState(false);


  const userSpeaking = isRecording && volume > 15;

  useEffect(() => {
    if (!isRecording || !wsRef.current) return;
    const interval = setInterval(() => {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        const silence = new Int16Array(480);
        wsRef.current.send(silence.buffer);
        console.log('📤 Sent silence packet');
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [isRecording]);

  useEffect(() => {
    if (isRecording) {
      setVolume(0);
      setAiSpeaking(false);
      return;
    }
    const interval = setInterval(() => {
      setVolume(Math.random() * 100);
    }, 100);
    return () => clearInterval(interval);
  }, [isRecording]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ws = new WebSocket('wss://aip2pcall-production.up.railway.app/ws-stt');
      // const ws = new WebSocket('ws://localhost:3001/ws-stt');
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onerror = (error) => console.error('WebSocket error:', error);
      ws.onclose = (event) => console.log('WebSocket closed:', event.code, event.reason);

      ws.onmessage = async (event) => {
        if (typeof event.data === 'string') {
          const message = JSON.parse(event.data);
      
          if (message.transcript && message.isFinal) {
            setAiThinking(true); // ✅ Show thinking before receiving audio
            if (currentAudioSourceRef.current) {
              try { currentAudioSourceRef.current.stop(); } catch (_) {}
              currentAudioSourceRef.current.disconnect();
              currentAudioSourceRef.current = null;
              setAiSpeaking(false);
            }
          }
      
          return;
        }
      
        if (event.data instanceof ArrayBuffer) {
          let audioCtx = audioCtxRef.current;
          if (!audioCtx || audioCtx.state === 'closed') {
            audioCtx = new AudioContext();
            audioCtxRef.current = audioCtx;
          }
      
          try {
            const audioBuffer = await audioCtx.decodeAudioData(event.data.slice(0));
            if (currentAudioSourceRef.current) {
              try { currentAudioSourceRef.current.stop(); } catch (_) {}
              currentAudioSourceRef.current.disconnect();
              currentAudioSourceRef.current = null;
            }
      
            const source = audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioCtx.destination);
            setAiThinking(false); // ✅ Audio has arrived — stop "thinking"
            setAiSpeaking(true);
            setIsRecording(false);
      
            source.onended = () => {
              setAiSpeaking(false);
              setIsRecording(true);
            };
            source.start(0);
            currentAudioSourceRef.current = source;
          } catch (err) {
            console.error('Error decoding audio from server:', err);
            setAiThinking(false);
            setAiSpeaking(false);
            setIsRecording(true);
          }
        }
      };
      

      const audioCtx = new AudioContext({ sampleRate: 48000 });
      await audioCtx.audioWorklet.addModule('audio-processor.js');
      audioCtxRef.current = audioCtx;
      if (audioCtx.state !== 'running') await audioCtx.resume();

      const source = audioCtx.createMediaStreamSource(stream);
      sourceRef.current = source;

      const workletNode = new AudioWorkletNode(audioCtx, 'pcm-worklet');
      workletNodeRef.current = workletNode;
      workletNode.port.onmessage = (event) => {
        const pcmBuffer = event.data;
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(pcmBuffer);
        }
      };

      source.connect(workletNode);
      const gainNode = audioCtx.createGain();
      gainNode.gain.value = 0;
      workletNode.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      setIsRecording(true);
    } catch (err) {
      console.error('Error initializing audio stream:', err);
    }
  };

  const stopRecording = () => {
    workletNodeRef.current?.disconnect();
    workletNodeRef.current?.port.close();
    workletNodeRef.current = null;

    sourceRef.current?.disconnect();
    sourceRef.current = null;

    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }

    if (currentAudioSourceRef.current) {
      try { currentAudioSourceRef.current.stop(); } catch (_) {}
      currentAudioSourceRef.current.disconnect();
      currentAudioSourceRef.current = null;
    }

    wsRef.current?.close();
    wsRef.current = null;

    setIsRecording(false);
    setAiSpeaking(false);
  };

  return (
    <div className="app-container">
      <h1 className="title">AI Talk Visualizer</h1>
  
      <button className="record-button" onClick={isRecording ? stopRecording : startRecording}>
        {isRecording ? 'Stop' : 'Start'} Talking
      </button>

      {aiThinking && (
        <div className="thinking-indicator">
          🤖 AI is thinking...
        </div>
      )}
  
      <div className="profiles">
        <RobotProfile isSpeaking={userSpeaking} isListening={false} label="You" />
        <RobotProfile isSpeaking={aiSpeaking} isListening={isRecording} label="AI" />
      </div>
    </div>
  );
  
}