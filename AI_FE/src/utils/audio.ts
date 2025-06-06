export function float32ToInt16(buffer: Float32Array): Int16Array {
    const l = buffer.length;
    const result = new Int16Array(l);
  
    for (let i = 0; i < l; i++) {
      const s = Math.max(-1, Math.min(1, buffer[i]));
      result[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
  
    return result;
  }
  