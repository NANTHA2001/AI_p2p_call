// public/audio-processor.js
class PCMWorkletProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input.length > 0) {
      const pcm = input[0]; // mono channel
      const pcmBuffer = new ArrayBuffer(pcm.length * 2);
      const view = new DataView(pcmBuffer);
      for (let i = 0; i < pcm.length; i++) {
        // Clamp sample between -1 and 1
        const s = Math.max(-1, Math.min(1, pcm[i]));
        // Convert float sample to 16-bit PCM little-endian
        view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      }
      this.port.postMessage(pcmBuffer);
    }
    return true;
  }
}

registerProcessor('pcm-worklet', PCMWorkletProcessor);
