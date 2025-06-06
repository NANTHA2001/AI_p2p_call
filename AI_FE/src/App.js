import React, { useState, useRef, useEffect } from 'react';

const USER_IMG = 'https://randomuser.me/api/portraits/men/32.jpg';
const AI_IMG = 'https://randomuser.me/api/portraits/women/65.jpg';

function ProfileWithWave({ img, isSpeaking, color }) {
  const [scale, setScale] = useState(1);

  useEffect(() => {
    if (!isSpeaking) {
      setScale(1);
      return;
    }
    let frameId;
    const animate = () => {
      const newScale = 1 + 0.3 * Math.abs(Math.sin(Date.now() / 300));
      setScale(newScale);
      frameId = requestAnimationFrame(animate);
    };
    animate();
    return () => cancelAnimationFrame(frameId);
  }, [isSpeaking]);

  return (
    <div style={{ position: 'relative', width: 150, height: 150, margin: 20 }}>
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: 150,
          height: 150,
          borderRadius: '50%',
          transform: `translate(-50%, -50%) scale(${scale})`,
          backgroundColor: color,
          opacity: isSpeaking ? 0.3 : 0,
          filter: 'blur(12px)',
          pointerEvents: 'none',
          transition: 'opacity 0.3s',
          zIndex: 0,
        }}
      />
      <img
        src={img}
        alt="profile"
        style={{
          width: 150,
          height: 150,
          borderRadius: '50%',
          border: `4px solid ${color}`,
          objectFit: 'cover',
          position: 'relative',
          zIndex: 1,
          boxShadow: isSpeaking
            ? `0 0 15px 5px ${color}`
            : '0 0 5px 1px rgba(0,0,0,0.3)',
          transition: 'box-shadow 0.3s',
        }}
      />
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

  // Simulate mic volume only (remove AI speaking timer simulation)
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

      const ws = new WebSocket('ws://127.0.0.1:3000/ws-stt');
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

            // Stop previous AI audio if any
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

            setAiSpeaking(true); // AI started speaking
            setIsRecording(false);

            source.onended = () => {
              setAiSpeaking(false); // AI stopped speaking
            };

            source.start(0);
            currentAudioSourceRef.current = source;
          } catch (err) {
            console.error('Error decoding audio from server:', err);
            setAiSpeaking(false);
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
            isSpeaking={userSpeaking}
            color="#4caf50"
          />
          <div style={{ marginTop: 10, fontWeight: 'bold' }}>You</div>
        </div>

        <div style={{ textAlign: 'center' }}>
          <ProfileWithWave
            img={AI_IMG}
            isSpeaking={aiSpeaking}
            color="#2196f3"
          />
          <div style={{ marginTop: 10, fontWeight: 'bold' }}>AI</div>
        </div>
      </div>
    </div>
  );
}
