'use client';

import { useEffect, useState } from 'react';

interface Note {
  _id: string;
  summary: string;
  discussed_topics: string[];
  action_items: string[];
  next_steps?: string;
  linked_safety_report_ids: string[];
  linked_compliance_flag_ids: string[];
}

interface WrapResponse {
  status: string;
  note?: Note;
}

interface Props {
  sessionId: string;
  onApprove: () => void;
}

export function WrapView({ sessionId, onApprove }: Props) {
  const [note, setNote] = useState<Note | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const r = await fetch(`http://localhost:8000/api/wrap/${sessionId}`);
        const d: WrapResponse = await r.json();
        if (d.status === 'ready' && d.note) {
          setNote(d.note);
          setLoading(false);
          clearInterval(poll);
        }
      } catch {}
    }, 1500);
    setTimeout(() => setLoading(false), 25000);
    return () => clearInterval(poll);
  }, [sessionId]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-8">
        <p className="text-xs font-medium uppercase tracking-widest text-slate-500">
          Call wrap · Dr Eleanor Rose
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-900">
          {loading ? 'Writing the note…' : 'Note ready for review'}
        </h1>
      </header>

      {loading && !note && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          The Action Agent is composing your CRM note. This usually takes 10 to 20 seconds.
        </div>
      )}

      {note && (
        <div className="space-y-4">
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Summary</p>
            <p className="mt-2 text-sm text-slate-900">{note.summary}</p>
            {note.discussed_topics?.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {note.discussed_topics.map((t, i) => (
                  <span key={i} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                    {t}
                  </span>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Action items</p>
            <ol className="mt-3 space-y-3">
              {note.action_items.map((a, i) => (
                <li key={i} className="flex gap-3 text-sm text-slate-900">
                  <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700">
                    {i + 1}
                  </span>
                  <span>{a}</span>
                </li>
              ))}
            </ol>
          </section>

          {(note.linked_safety_report_ids.length > 0 || note.linked_compliance_flag_ids.length > 0) && (
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Linked flags</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {note.linked_safety_report_ids.map((id) => (
                  <span key={id} className="rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">
                    Safety · {id.slice(0, 10)}
                  </span>
                ))}
                {note.linked_compliance_flag_ids.map((id) => (
                  <span key={id} className="rounded-md bg-rose-50 px-2 py-1 text-xs font-medium text-rose-800">
                    Compliance · {id.slice(0, 10)}
                  </span>
                ))}
              </div>
            </section>
          )}

          {note.next_steps && (
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Next steps</p>
              <p className="mt-2 text-sm text-slate-900">{note.next_steps}</p>
            </section>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              onClick={onApprove}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
            >
              Approve and send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}