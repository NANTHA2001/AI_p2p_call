import React, { useState, useRef, useEffect } from 'react';
import './App.css'; // assuming your CSS is in App.css

const USER_IMG = 'https://randomuser.me/api/portraits/men/32.jpg';
// const AI_IMG = 'https://randomuser.me/api/portraits/women/65.jpg';
// const AI_IMG_TALKING = 'https://randomuser.me/api/portraits/women/66.jpg'; // Simulated mouth-open image
const AI_IMG = 'https://randomuser.me/api/portraits/women/65.jpg';

// AI talking image (simulated mouth open)
const AI_IMG_TALKING = 'https://randomuser.me/api/portraits/women/66.jpg';


function ProfileWithWave({ img, imgTalking, isSpeaking, isListening, color }) {
  const headShakeStyle = isListening
    ? {
        animation: 'head-listening 1.5s infinite ease-in-out',
        transformOrigin: 'center bottom',
      }
    : {};

  const speakingGlowStyle = isSpeaking
    ? {
        animation: 'speaking-glow 1s infinite',
      }
    : {};

  return (
    <div style={{ position: 'relative', width: 150, height: 150, margin: 20 }}>
      {/* Background pulse while speaking */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: 150,
          height: 150,
          borderRadius: '50%',
          transform: `translate(-50%, -50%)`,
          backgroundColor: color,
          opacity: isSpeaking ? 0.3 : 0,
          filter: 'blur(12px)',
          pointerEvents: 'none',
          transition: 'opacity 0.3s',
          zIndex: 0,
        }}
      />

      {/* AI face container */}
      <div
        style={{
          width: 150,
          height: 150,
          borderRadius: '50%',
          border: `4px solid ${color}`,
          position: 'relative',
          overflow: 'hidden',
          zIndex: 1,
          backgroundColor: '#fff',
          ...speakingGlowStyle,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        {/* AI head image */}
        <img
          src={isSpeaking ? imgTalking : img}
          alt="AI"
          style={{
            width: '90%',
            height: '90%',
            borderRadius: '50%',
            objectFit: 'cover',
            ...headShakeStyle,
          }}
        />
      </div>
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

    return () => {
      clearInterval(interval);
    };
  }, [isRecording]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const ws = new WebSocket('wss://aip2pcall-production.up.railway.app/ws-stt');
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onerror = (error) => console.error('WebSocket error:', error);
      ws.onclose = (event) => console.log('WebSocket closed:', event.code, event.reason);

      ws.onmessage = async (event) => {
        if (event.data instanceof ArrayBuffer) {
          let audioCtx = audioCtxRef.current;
          if (!audioCtx || audioCtx.state === 'closed') {
            audioCtx = new AudioContext();
            audioCtxRef.current = audioCtx;
          }
          try {
            const audioBuffer = await audioCtx.decodeAudioData(event.data.slice(0));

            if (currentAudioSourceRef.current) {
              try {
                currentAudioSourceRef.current.stop();
              } catch (_) {}
              currentAudioSourceRef.current.disconnect();
              currentAudioSourceRef.current = null;
            }

            const source = audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioCtx.destination);

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
            setAiSpeaking(false);
            setIsRecording(true);
          }
        }
      };

      const audioCtx = new AudioContext({ sampleRate: 48000 });
      await audioCtx.audioWorklet.addModule('audio-processor.js');
      audioCtxRef.current = audioCtx;

      if (audioCtx.state !== 'running') {
        await audioCtx.resume();
      }

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
      try {
        currentAudioSourceRef.current.stop();
      } catch (_) {}
      currentAudioSourceRef.current.disconnect();
      currentAudioSourceRef.current = null;
    }

    wsRef.current?.close();
    wsRef.current = null;

    setIsRecording(false);
    setAiSpeaking(false);
  };

  return (
    <div
      style={{
        backgroundColor: '#111',
        color: '#eee',
        minHeight: '100vh',
        padding: 20,
        fontFamily: 'Arial, sans-serif',
      }}
    >
      <h2 style={{ textAlign: 'center' }}>Audio Streaming Visualizer</h2>
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <button
          onClick={isRecording ? stopRecording : startRecording}
          style={{
            padding: '12px 24px',
            fontSize: 18,
            backgroundColor: isRecording ? '#b33' : '#3b3',
            border: 'none',
            borderRadius: 8,
            color: '#fff',
            cursor: 'pointer',
          }}
        >
          {isRecording ? 'Stop' : 'Start'} Recording
        </button>
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          gap: 60,
          alignItems: 'center',
          marginTop: 50,
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <ProfileWithWave
            img={USER_IMG}
            imgTalking={USER_IMG}
            isSpeaking={userSpeaking}
            isListening={false}
            color="#4caf50"
          />
          <div style={{ marginTop: 10, fontWeight: 'bold' }}>You</div>
        </div>

        <div style={{ textAlign: 'center' }}>
          <ProfileWithWave
            img={AI_IMG}
            imgTalking={AI_IMG_TALKING}
            isSpeaking={aiSpeaking}
            isListening={isRecording}
            color="#2196f3"
          />
          <div style={{ marginTop: 10, fontWeight: 'bold' }}>AI</div>
        </div>
      </div>
    </div>
  );
}