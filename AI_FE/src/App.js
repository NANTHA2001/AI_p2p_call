import React, { useState, useRef } from 'react';

export default function App() {
  const [isRecording, setIsRecording] = useState(false);

  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const workletNodeRef = useRef(null);
  const sourceRef = useRef(null);
  const currentAudioSourceRef = useRef(null); // 👈 Track currently playing audio

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

            // 🔇 Stop the previous audio if still playing
            if (currentAudioSourceRef.current) {
              try {
                currentAudioSourceRef.current.stop();
              } catch (_) {}
              currentAudioSourceRef.current.disconnect();
              currentAudioSourceRef.current = null;
            }

            // 🎧 Play new audio
            const source = audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioCtx.destination);
            source.start(0);

            currentAudioSourceRef.current = source;
          } catch (err) {
            console.error('Error decoding audio from server:', err);
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

    // 🔇 Stop any ongoing TTS playback
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
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>Audio Streaming (WebSocket)</h2>
      <button onClick={isRecording ? stopRecording : startRecording}>
        {isRecording ? 'Stop' : 'Start'} Recording
      </button>
    </div>
  );
}
