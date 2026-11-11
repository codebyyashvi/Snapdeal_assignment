import { Keyboard, Mic, Phone, PhoneOff, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

const STATUS = {
  idle: { label: 'Ready to call', hint: 'Tap the button and speak naturally - no need to press anything while talking.' },
  connecting: { label: 'Connecting...', hint: 'Allow microphone access when prompted.' },
  speaking: { label: 'Nalini is speaking', hint: '' },
  listening: { label: 'Listening...', hint: 'Go ahead, I am listening.' },
  hearing: { label: 'Hearing you...', hint: 'I will reply when you pause.' },
  thinking: { label: 'Thinking...', hint: 'Transcribing and analysing your account.' },
  ended: { label: 'Call ended', hint: 'Summary and action plan saved to the case file.' },
}

const STAGES = ['discovery', 'diagnosis', 'recommendation', 'commitment', 'closing']

export default function CallPanel({ status, level, messages, onStart, onEnd, onSendText, allowBargeIn, setAllowBargeIn, stage }) {
  const [text, setText] = useState('')
  const [showText, setShowText] = useState(false)
  const scrollRef = useRef(null)
  const live = !['idle', 'ended'].includes(status)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const orbColor = {
    speaking: 'bg-brand',
    listening: 'bg-emerald-500',
    hearing: 'bg-emerald-600',
    thinking: 'bg-amber-500',
    connecting: 'bg-slate-400',
  }[status] || 'bg-slate-300'

  const scale = status === 'hearing' || status === 'listening' ? 1 + level * 0.5 : 1
  const stageIndex = STAGES.indexOf(stage === 'closed' ? 'closing' : stage)

  return (
    <section className="rounded-2xl bg-white shadow-sm border border-slate-200 flex flex-col h-[calc(100vh-110px)] min-h-[560px]">
      <div className="p-6 flex flex-col items-center border-b border-slate-100">
        <div className="relative h-32 w-32 flex items-center justify-center">
          {(status === 'speaking' || status === 'hearing') && (
            <span className={`absolute inset-0 rounded-full ${orbColor} animate-ring`} />
          )}
          <div
            className={`relative h-28 w-28 rounded-full ${orbColor} shadow-lg flex items-center justify-center transition-all duration-100`}
            style={{ transform: `scale(${scale})` }}
          >
            {status === 'thinking' ? (
              <div className="flex gap-1.5">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="h-2.5 w-2.5 rounded-full bg-white animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            ) : (
              <Mic className="h-10 w-10 text-white" />
            )}
          </div>
        </div>
        <div className="mt-4 text-lg font-semibold">{STATUS[status].label}</div>
        <div className="text-sm text-slate-500 min-h-5 text-center max-w-sm">{STATUS[status].hint}</div>

        <div className="mt-4 flex items-center gap-3">
          {!live ? (
            <button onClick={onStart} className="flex items-center gap-2 rounded-full bg-brand hover:bg-brand-dark text-white px-6 py-3 font-semibold shadow">
              <Phone className="h-5 w-5" /> {status === 'ended' ? 'Call again' : 'Call Virtual KAM'}
            </button>
          ) : (
            <button onClick={onEnd} className="flex items-center gap-2 rounded-full bg-slate-800 hover:bg-slate-900 text-white px-6 py-3 font-semibold shadow">
              <PhoneOff className="h-5 w-5" /> End call
            </button>
          )}
        </div>
        <label className="mt-3 flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
          <input type="checkbox" checked={allowBargeIn} onChange={(e) => setAllowBargeIn(e.target.checked)} className="accent-brand" />
          Allow interrupting the bot (best with headphones)
        </label>

        {stage && (
          <div className="mt-4 flex w-full gap-1">
            {STAGES.map((s, i) => (
              <div key={s} className="flex-1">
                <div className={`h-1.5 rounded-full ${i <= stageIndex ? 'bg-brand' : 'bg-slate-200'}`} />
                <div className={`mt-1 text-[10px] uppercase tracking-wide text-center ${i === stageIndex ? 'text-brand font-semibold' : 'text-slate-400'}`}>{s}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-sm text-slate-400 text-center mt-8">
            Try saying: "My sales have dropped significantly this month. I don't understand why. Can you help me?"
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${m.role === 'user' ? 'bg-slate-800 text-white rounded-br-sm' : 'bg-rose-50 text-slate-800 rounded-bl-sm'}`}>
              <div className={`text-[10px] font-semibold uppercase mb-0.5 ${m.role === 'user' ? 'text-slate-300' : 'text-brand'}`}>
                {m.role === 'user' ? 'Seller' : 'Nalini - Virtual KAM'}
              </div>
              {m.text}
              {m.timings && Object.keys(m.timings).length > 0 && (
                <div className="mt-1 text-[10px] text-slate-400">
                  {Object.entries(m.timings).map(([k, v]) => `${k.toUpperCase()} ${v}s`).join(' · ')}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-slate-100 p-3">
        {showText ? (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (text.trim()) onSendText(text.trim())
              setText('')
            }}
            className="flex gap-2"
          >
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={!live}
              placeholder={live ? 'Type a message (fallback)...' : 'Start a call first'}
              className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-brand"
            />
            <button disabled={!live} className="rounded-lg bg-slate-800 text-white px-3 disabled:opacity-40">
              <Send className="h-4 w-4" />
            </button>
          </form>
        ) : (
          <button onClick={() => setShowText(true)} className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1 mx-auto">
            <Keyboard className="h-3.5 w-3.5" /> Mic not working? Type instead
          </button>
        )}
      </div>
    </section>
  )
}
