'use client';

import { useEffect, useState } from 'react';
import { useVoiceAssistant } from '@livekit/components-react';

interface Brief {
  headline?: string;
  last_interaction_summary?: string;
  recommended_opener?: string;
  key_concerns?: string[];
}

interface Props {
  sessionId: string;
  onStartCall: () => void;
}

export function PrepView({ sessionId, onStartCall }: Props) {
  const { state } = useVoiceAssistant();
  const [brief, setBrief] = useState<Brief | null>(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const r = await fetch(`http://localhost:8000/api/brief/${sessionId}`);
        const d = await r.json();
        if (d.status === 'ready') {
          setBrief(d.brief);
          clearInterval(interval);
        }
      } catch {}
    }, 1500);
    return () => clearInterval(interval);
  }, [sessionId]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-8">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-500">
          Pre-call brief · Dr Eleanor Rose
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-900">
          Preparing your call
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Say &quot;prep me for Dr Rose&quot; — your assistant will brief you in under 30 seconds.
        </p>
      </header>

      <div className="mb-6 flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm">
        <span
          className={`h-2 w-2 rounded-full ${
            state === 'listening' || state === 'thinking' || state === 'speaking'
              ? 'animate-pulse bg-emerald-500'
              : 'bg-slate-300'
          }`}
        />
        <span className="text-slate-700">
          {state === 'connecting' && 'Connecting'}
          {state === 'listening' && 'Listening — say "prep me"'}
          {state === 'thinking' && 'Retrieving brief'}
          {state === 'speaking' && 'Speaking the brief'}
          {state === 'disconnected' && 'Disconnected'}
          {!state && 'Initialising'}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card title="Headline" body={brief?.headline} />
        <Card title="Last interaction" body={brief?.last_interaction_summary} />
        <Card title="Recommended opener" body={brief?.recommended_opener} />
        <ConcernsCard concerns={brief?.key_concerns} />
      </div>

      <div className="mt-8 flex justify-end">
        <button
          onClick={onStartCall}
          disabled={!brief}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          I&apos;m on the call
        </button>
      </div>
    </div>
  );
}

function Card({ title, body }: { title: string; body?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-widest text-slate-500">{title}</p>
      <p className="mt-2 text-sm text-slate-900">
        {body ?? <span className="text-slate-400">…</span>}
      </p>
    </div>
  );
}

function ConcernsCard({ concerns }: { concerns?: string[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Key concerns</p>
      {concerns && concerns.length > 0 ? (
        <ul className="mt-2 space-y-1 text-sm text-slate-900">
          {concerns.map((c, i) => (
            <li key={i}>· {c}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-400">…</p>
      )}
    </div>
  );
}