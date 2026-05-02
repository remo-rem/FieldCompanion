'use client';

import { useEffect, useState } from 'react';

interface Flag {
  _id: string;
  detected_at: string;
  trigger_text: string;
  rationale?: string;
  abpi_clause?: string;
  trigger_category?: string;
  severity: string;
}

interface FlagsResponse {
  safety: Flag[];
  compliance: Flag[];
}

interface Props {
  sessionId: string;
  onEndCall: () => void;
}

export function CallView({ sessionId, onEndCall }: Props) {
  const [safety, setSafety] = useState<Flag[]>([]);
  const [compliance, setCompliance] = useState<Flag[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const tick = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(tick);
  }, []);

  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const r = await fetch(`http://localhost:8000/api/flags/${sessionId}`);
        const d: FlagsResponse = await r.json();
        setSafety(d.safety || []);
        setCompliance(d.compliance || []);
      } catch {}
    }, 1500);
    return () => clearInterval(poll);
  }, [sessionId]);

  const liveFlags = [
    ...safety.map((f) => ({ ...f, kind: 'safety' as const })),
    ...compliance.map((f) => ({ ...f, kind: 'compliance' as const })),
  ].filter((f) => !dismissed.has(f._id));

  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const ss = String(elapsed % 60).padStart(2, '0');

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <header className="mb-6 flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-slate-500">
            On call · Dr Eleanor Rose
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">
            Recording · {mm}:{ss}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700">
            <span className="h-2 w-2 animate-pulse rounded-full bg-rose-500" />
            Live
          </span>
          <button
            onClick={onEndCall}
            className="rounded-lg bg-rose-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-rose-700"
          >
            End call
          </button>
        </div>
      </header>

      <div className="space-y-3">
        {liveFlags.length === 0 && (
          <div className="rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-500">
            No flags raised. Field Companion is listening silently.
          </div>
        )}
        {liveFlags.map((f) => (
          <div
            key={f._id}
            className={`flex items-start gap-3 rounded-xl border px-5 py-4 ${
              f.kind === 'safety'
                ? 'border-amber-200 bg-amber-50'
                : 'border-rose-200 bg-rose-50'
            }`}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs font-semibold uppercase tracking-widest ${
                    f.kind === 'safety' ? 'text-amber-800' : 'text-rose-800'
                  }`}
                >
                  {f.kind === 'safety' ? 'Safety awareness' : 'Compliance awareness'}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    f.kind === 'safety'
                      ? 'bg-amber-200 text-amber-900'
                      : 'bg-rose-200 text-rose-900'
                  }`}
                >
                  {f.kind === 'safety'
                    ? f.trigger_category?.replace(/_/g, ' ')
                    : f.abpi_clause}
                </span>
              </div>
              <p className="mt-2 text-sm italic text-slate-800">&ldquo;{f.trigger_text}&rdquo;</p>
              {f.rationale && <p className="mt-1 text-xs text-slate-600">{f.rationale}</p>}
            </div>
            <button
              onClick={() => setDismissed((s) => new Set(s).add(f._id))}
              className="rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-white/50"
            >
              Dismiss
            </button>
          </div>
        ))}
      </div>

      <p className="mt-8 text-center text-xs text-slate-400">
        Field Companion is silent during calls · banners are awareness only · the rep remains in control
      </p>
    </div>
  );
}