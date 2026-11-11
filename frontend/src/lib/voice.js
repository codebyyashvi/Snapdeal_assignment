// Hands-free microphone capture with energy-based voice activity detection.
// Emits one 16 kHz mono WAV per utterance (Gnani STT accepts WAV, not WebM).

const TARGET_RATE = 16000
const FRAME = 2048
const END_SILENCE_MS = 1100
const MIN_SPEECH_MS = 350
const MAX_UTTERANCE_MS = 25000 // Gnani REST STT limit is 30 s
const PREROLL_MS = 400

export class VoiceEngine {
  constructor({ onUtterance, onLevel, onSpeechStart, onBargeIn }) {
    this.onUtterance = onUtterance
    this.onLevel = onLevel
    this.onSpeechStart = onSpeechStart
    this.onBargeIn = onBargeIn
    this.mode = 'off' // off | listen | barge
    this.noiseFloor = 0.01
    this.reset()
  }

  reset() {
    this.capturing = false
    this.chunks = []
    this.preroll = []
    this.loudFrames = 0
    this.silenceMs = 0
    this.speechMs = 0
    this.totalMs = 0
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    })
    this.ctx = new AudioContext()
    this.source = this.ctx.createMediaStreamSource(this.stream)
    this.processor = this.ctx.createScriptProcessor(FRAME, 1, 1)
    this.frameMs = (FRAME / this.ctx.sampleRate) * 1000
    this.processor.onaudioprocess = (e) => this.process(e.inputBuffer.getChannelData(0))
    this.source.connect(this.processor)
    this.processor.connect(this.ctx.destination)
  }

  stop() {
    this.mode = 'off'
    this.processor?.disconnect()
    this.source?.disconnect()
    this.stream?.getTracks().forEach((t) => t.stop())
    this.ctx?.close()
    this.ctx = null
  }

  setMode(mode) {
    this.mode = mode
    this.reset()
  }

  process(input) {
    const frame = new Float32Array(input)
    let sum = 0
    for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i]
    const rms = Math.sqrt(sum / frame.length)
    this.onLevel?.(Math.min(1, rms * 12))

    if (this.mode === 'off') return

    if (!this.capturing) {
      this.noiseFloor = this.noiseFloor * 0.95 + Math.min(rms, 0.05) * 0.05
      const threshold = this.mode === 'barge' ? Math.max(0.06, this.noiseFloor * 6) : Math.max(0.018, this.noiseFloor * 3)
      const framesNeeded = this.mode === 'barge' ? 6 : 3

      this.preroll.push(frame)
      if (this.preroll.length * this.frameMs > PREROLL_MS) this.preroll.shift()

      this.loudFrames = rms > threshold ? this.loudFrames + 1 : 0
      if (this.loudFrames >= framesNeeded) {
        if (this.mode === 'barge') this.onBargeIn?.()
        this.mode = 'listen'
        this.capturing = true
        this.chunks = [...this.preroll]
        this.onSpeechStart?.()
      }
      return
    }

    this.chunks.push(frame)
    this.totalMs += this.frameMs
    const threshold = Math.max(0.014, this.noiseFloor * 2.5)
    if (rms > threshold) {
      this.speechMs += this.frameMs
      this.silenceMs = 0
    } else {
      this.silenceMs += this.frameMs
    }

    const done = (this.silenceMs > END_SILENCE_MS && this.speechMs > MIN_SPEECH_MS) || this.totalMs > MAX_UTTERANCE_MS
    const falseStart = this.silenceMs > END_SILENCE_MS && this.speechMs <= MIN_SPEECH_MS
    if (falseStart) {
      this.reset()
    } else if (done) {
      const wav = encodeWav(downsample(concat(this.chunks), this.ctx.sampleRate, TARGET_RATE), TARGET_RATE)
      this.mode = 'off'
      this.reset()
      this.onUtterance?.(wav)
    }
  }
}

function concat(chunks) {
  const out = new Float32Array(chunks.reduce((n, c) => n + c.length, 0))
  let offset = 0
  for (const c of chunks) {
    out.set(c, offset)
    offset += c.length
  }
  return out
}

function downsample(buffer, fromRate, toRate) {
  if (fromRate === toRate) return buffer
  const ratio = fromRate / toRate
  const out = new Float32Array(Math.floor(buffer.length / ratio))
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(Math.floor((i + 1) * ratio), buffer.length)
    let sum = 0
    for (let j = start; j < end; j++) sum += buffer[j]
    out[i] = sum / Math.max(1, end - start)
  }
  return out
}

function encodeWav(samples, rate) {
  const buf = new ArrayBuffer(44 + samples.length * 2)
  const v = new DataView(buf)
  const str = (o, s) => [...s].forEach((ch, i) => v.setUint8(o + i, ch.charCodeAt(0)))
  str(0, 'RIFF')
  v.setUint32(4, 36 + samples.length * 2, true)
  str(8, 'WAVE')
  str(12, 'fmt ')
  v.setUint32(16, 16, true)
  v.setUint16(20, 1, true)
  v.setUint16(22, 1, true)
  v.setUint32(24, rate, true)
  v.setUint32(28, rate * 2, true)
  v.setUint16(32, 2, true)
  v.setUint16(34, 16, true)
  str(36, 'data')
  v.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([buf], { type: 'audio/wav' })
}

// Plays base64 WAV replies; resolves when playback ends or is interrupted.
export class Speaker {
  constructor() {
    this.audio = null
    this.resolve = null
  }

  play(base64) {
    this.stop()
    if (!base64) return Promise.resolve()
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))
    const url = URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' }))
    this.audio = new Audio(url)
    return new Promise((resolve) => {
      this.resolve = () => {
        URL.revokeObjectURL(url)
        this.resolve = null
        resolve()
      }
      this.audio.onended = this.resolve
      this.audio.onerror = this.resolve
      this.audio.play().catch(this.resolve)
    })
  }

  stop() {
    if (this.audio) {
      this.audio.pause()
      this.audio = null
    }
    this.resolve?.()
  }
}
