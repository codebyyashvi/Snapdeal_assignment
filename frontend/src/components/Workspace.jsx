import { AlertTriangle, CalendarClock, CheckCircle2, ClipboardList, History, MessageSquareQuote, Store } from 'lucide-react'

const inr = (n) => `₹${Number(n).toLocaleString('en-IN')}`

function formatMetric(value, unit) {
  if (unit === 'inr') return inr(value)
  if (unit === 'pct') return `${value}%`
  return value
}

// For these metrics an increase is bad.
const HIGHER_IS_WORSE = new Set(['cancellation_rate', 'oos_products'])

const SEVERITY = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-slate-100 text-slate-600',
}

function Card({ icon: Icon, title, right, children }) {
  return (
    <section className="rounded-2xl bg-white shadow-sm border border-slate-200 p-5">
      <div className="flex items-center gap-2 mb-3">
        {Icon && <Icon className="h-4 w-4 text-brand" />}
        <h2 className="font-semibold text-sm uppercase tracking-wide text-slate-600">{title}</h2>
        <div className="ml-auto">{right}</div>
      </div>
      {children}
    </section>
  )
}

export default function Workspace({ seller, callState, history, onClearHistory }) {
  if (!seller) return <div className="text-slate-400 p-8">Loading seller account...</div>
  const { seller: s, metrics, diagnosis } = seller
  const confirmed = new Set(callState?.confirmed_issues || [])
  const plan = callState?.action_plan || []
  const facts = callState?.seller_facts || []
  const summary = callState?.summary

  return (
    <div className="space-y-5">
      <Card
        icon={Store}
        title="Seller account"
        right={<span className="text-xs text-slate-400">{s.seller_id}</span>}
      >
        <div className="flex flex-wrap items-baseline gap-x-3">
          <div className="text-xl font-bold">{s.store}</div>
          <div className="text-sm text-slate-500">
            {s.name} · {s.category} · {s.city} · Rating {s.rating_last_month} → {s.rating_this_month}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-2">
          {Object.entries(metrics).map(([key, m]) => {
            const delta = m.this - m.last
            const pct = m.last ? Math.round((delta / m.last) * 1000) / 10 : 0
            const bad = HIGHER_IS_WORSE.has(key) ? delta > 0 : delta < 0
            return (
              <div key={key} className="rounded-xl bg-slate-50 p-3">
                <div className="text-[11px] text-slate-500 leading-tight h-7">{m.label}</div>
                <div className="text-lg font-bold">{formatMetric(m.this, m.unit)}</div>
                <div className="text-[11px] text-slate-400">was {formatMetric(m.last, m.unit)}</div>
                <div className={`text-xs font-semibold ${delta === 0 ? 'text-slate-500' : bad ? 'text-red-600' : 'text-emerald-600'}`}>
                  {delta === 0 ? 'No change' : `${delta > 0 ? '+' : ''}${m.unit === 'pct' ? `${delta} pts` : `${pct}%`}`}
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      <Card icon={AlertTriangle} title="AI diagnosis (run before the call)">
        <p className="text-sm font-medium mb-3">{diagnosis.headline}</p>
        <div className="space-y-2">
          {diagnosis.issues.map((issue) => (
            <div key={issue.id} className={`rounded-xl border p-3 transition-colors ${confirmed.has(issue.id) ? 'border-emerald-300 bg-emerald-50/50' : 'border-slate-200'}`}>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-bold uppercase rounded px-1.5 py-0.5 ${SEVERITY[issue.severity]}`}>{issue.severity}</span>
                <span className="font-semibold text-sm">{issue.title}</span>
                {issue.est_monthly_impact_inr > 0 && (
                  <span className="text-xs text-slate-500">~{inr(issue.est_monthly_impact_inr)}/mo at stake</span>
                )}
                {confirmed.has(issue.id) && (
                  <span className="ml-auto flex items-center gap-1 text-xs font-semibold text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Confirmed on call
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-600 mt-1">{issue.evidence}</p>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-5 md:grid-cols-2">
        <Card icon={MessageSquareQuote} title="Learned from seller">
          {facts.length === 0 ? (
            <p className="text-sm text-slate-400">Root causes the seller shares will appear here.</p>
          ) : (
            <ul className="space-y-1.5">
              {facts.map((f) => (
                <li key={f} className="text-sm flex gap-2">
                  <span className="text-brand">•</span>
                  {f}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card icon={CalendarClock} title="Follow-up owned by KAM">
          {callState?.follow_up ? (
            <div>
              <div className="text-lg font-bold">{callState.follow_up.date}</div>
              <div className="text-sm text-slate-600">{callState.follow_up.purpose}</div>
            </div>
          ) : (
            <p className="text-sm text-slate-400">The KAM books a follow-up once a plan is agreed.</p>
          )}
        </Card>
      </div>

      <Card icon={ClipboardList} title="Action plan" right={plan.length > 0 && <span className="text-xs text-slate-400">{plan.filter((a) => a.status === 'agreed').length}/{plan.length} agreed</span>}>
        {plan.length === 0 ? (
          <p className="text-sm text-slate-400">The KAM builds the plan live during the call.</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {plan.map((a, i) => (
              <div key={i} className="py-2.5 flex items-start gap-3">
                <span className={`mt-0.5 text-[10px] font-bold uppercase rounded px-1.5 py-0.5 ${a.owner === 'kam' ? 'bg-brand text-white' : 'bg-slate-800 text-white'}`}>
                  {a.owner === 'kam' ? 'KAM' : 'Seller'}
                </span>
                <div className="flex-1">
                  <div className="text-sm font-medium">{a.title}</div>
                  <div className="text-xs text-slate-500">{a.impact}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-semibold">{a.due}</div>
                  <div className={`text-[10px] uppercase font-semibold ${a.status === 'agreed' ? 'text-emerald-600' : 'text-amber-600'}`}>{a.status}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {summary && (
        <Card icon={CheckCircle2} title="Call summary (saved to case file)" right={summary.seller_sentiment && <span className="text-xs text-slate-500">Sentiment: {summary.seller_sentiment}</span>}>
          <div className="grid gap-4 md:grid-cols-3 text-sm">
            {[
              ['Key issues', summary.key_issues],
              ['Recommendations', summary.recommendations],
              ['Next steps', summary.next_steps],
            ].map(([label, items]) => (
              <div key={label}>
                <div className="font-semibold mb-1">{label}</div>
                <ul className="space-y-1 list-disc pl-4 text-slate-600">
                  {(items || []).map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      )}

      {history.length > 0 && (
        <Card
          icon={History}
          title="Previous calls (agent memory)"
          right={<button onClick={onClearHistory} className="text-xs text-slate-400 hover:text-brand">Clear memory</button>}
        >
          <div className="space-y-2">
            {history.slice(0, 4).map((h) => (
              <div key={h._id} className="text-sm border-l-2 border-brand pl-3">
                <div className="text-xs text-slate-400">{new Date(h.ended_at).toLocaleString('en-IN')}</div>
                <div>{h.summary?.key_issues?.[0]}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
