import { useEffect, useRef, useState } from 'react'
import CallPanel from './components/CallPanel'
import Workspace from './components/Workspace'
import { api } from './lib/api'
import { Speaker, VoiceEngine } from './lib/voice'

export default function App() {
  const [seller, setSeller] = useState(null)
  const [health, setHealth] = useState(null)
  const [history, setHistory] = useState([])
  const [status, setStatus] = useState('idle') // idle | connecting | speaking | listening | hearing | thinking | ended
  const [messages, setMessages] = useState([])
  const [callState, setCallState] = useState(null)
  const [level, setLevel] = useState(0)
  const [error, setError] = useState('')
  const [allowBargeIn, setAllowBargeIn] = useState(false)

  const sessionRef = useRef(null)
  const vadRef = useRef(null)
  const speakerRef = useRef(new Speaker())
  const bargeRef = useRef(allowBargeIn)
  const endedRef = useRef(false)

  useEffect(() => {
    bargeRef.current = allowBargeIn
  }, [allowBargeIn])

  useEffect(() => {
    api.seller().then(setSeller).catch((e) => setError(String(e)))
    api.health().then(setHealth).catch(() => {})
    api.history().then(setHistory).catch(() => {})
  }, [])

  const addMessage = (role, text, extra = {}) =>
    setMessages((m) => [...m, { role, text, id: crypto.randomUUID(), ...extra }])

  async function speak(audio) {
    const vad = vadRef.current
    setStatus('speaking')
    vad?.setMode(bargeRef.current ? 'barge' : 'off')
    await speakerRef.current.play(audio)
    if (endedRef.current) return
    if (vad && !vad.capturing) {
      vad.setMode('listen')
      setStatus('listening')
    }
  }

  async function handleReply(res, userText) {
    if (userText !== undefined) {
      addMessage('user', res.transcript || userText || '(no speech detected)')
    }
    addMessage('assistant', res.reply, { timings: res.timings })
    setCallState(res.state)
    if (res.end_call) endedRef.current = true
    await speak(res.audio)
    if (res.end_call) finish()
  }

  function finish() {
    endedRef.current = true
    vadRef.current?.stop()
    vadRef.current = null
    setStatus('ended')
    setLevel(0)
    api.history().then(setHistory).catch(() => {})
  }

  async function onUtterance(wav) {
    const id = sessionRef.current
    if (!id || endedRef.current) return
    setStatus('thinking')
    try {
      const res = await api.sendAudio(id, wav)
      await handleReply(res, '')
    } catch (e) {
      setError(String(e))
      vadRef.current?.setMode('listen')
      setStatus('listening')
    }
  }

  async function startCall() {
    setError('')
    setMessages([])
    setCallState(null)
    endedRef.current = false
    setStatus('connecting')
    try {
      const vad = new VoiceEngine({
        onUtterance,
        onLevel: setLevel,
        onSpeechStart: () => setStatus('hearing'),
        onBargeIn: () => speakerRef.current.stop(),
      })
      await vad.start()
      vadRef.current = vad
      const res = await api.startSession()
      sessionRef.current = res.state.id
      await handleReply(res)
    } catch (e) {
      setError(`Could not start call: ${e.message || e}`)
      finish()
      setStatus('idle')
    }
  }

  async function endCall() {
    const id = sessionRef.current
    if (!id) return
    endedRef.current = true
    speakerRef.current.stop()
    vadRef.current?.setMode('off')
    setStatus('thinking')
    try {
      const res = await api.endSession(id)
      addMessage('assistant', res.reply)
      setCallState(res.state)
      setStatus('speaking')
      await speakerRef.current.play(res.audio)
    } catch (e) {
      setError(String(e))
    }
    finish()
  }

  async function sendText(text) {
    const id = sessionRef.current
    if (!id || endedRef.current) return
    speakerRef.current.stop()
    vadRef.current?.setMode('off')
    setStatus('thinking')
    try {
      await handleReply(await api.sendText(id, text), text)
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-slate-200">
        <div className="mx-auto max-w-7xl px-6 py-3 flex items-center gap-4">
          <div className="text-2xl font-extrabold tracking-tight text-brand">snapdeal</div>
          <div className="h-6 w-px bg-slate-200" />
          <div>
            <div className="font-semibold leading-tight">Virtual KAM</div>
            <div className="text-xs text-slate-500">AI Key Account Manager - voice</div>
          </div>
          <div className="ml-auto flex flex-wrap gap-2 text-xs">
            {health?.llm_providers?.[0] && (
              <span className="rounded-full bg-slate-100 px-2.5 py-1">LLM: {callState?.llm_provider || health.llm_providers[0]}</span>
            )}
            <span className="rounded-full bg-slate-100 px-2.5 py-1">STT/TTS: Gnani Vachana</span>
            <span className={`rounded-full px-2.5 py-1 ${health?.mongo ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
              {health?.mongo ? 'MongoDB memory on' : 'In-memory only'}
            </span>
          </div>
        </div>
      </header>

      {error && (
        <div className="mx-auto max-w-7xl px-6 pt-4">
          <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-2 flex justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')} className="font-semibold">Dismiss</button>
          </div>
        </div>
      )}

      <main className="mx-auto max-w-7xl px-6 py-5 grid gap-5 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <CallPanel
            status={status}
            level={level}
            messages={messages}
            onStart={startCall}
            onEnd={endCall}
            onSendText={sendText}
            allowBargeIn={allowBargeIn}
            setAllowBargeIn={setAllowBargeIn}
            stage={callState?.stage}
          />
        </div>
        <div className="lg:col-span-7">
          <Workspace
            seller={seller}
            callState={callState}
            history={history}
            onClearHistory={() => api.clearHistory().then(() => setHistory([]))}
          />
        </div>
      </main>
    </div>
  )
}
