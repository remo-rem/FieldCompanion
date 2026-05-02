'use client';

import { useEffect, useState } from 'react';

interface HcpProfile {
  full_name: string;
  title: string;
  affiliation: { trust: string; site: string };
  subspecialty: string;
  next_call: { scheduled_at: string; topic: string; location: string };
  consent: { consent_recorded_at: string };
}

interface Props {
  onStartPrep: () => void;
}

export function DashboardView({ onStartPrep }: Props) {
  const [hcp, setHcp] = useState<HcpProfile | null>(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/hcp/hcp_rose')
      .then((r) => r.json())
      .then(setHcp)
      .catch(() => setHcp(null));
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-8 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-slate-500">
            Field Companion · UK Oncology
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-900">
            Today&apos;s calls
          </h1>
        </div>
        <p className="text-sm text-slate-500">Rep: R. Patel</p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-slate-500">
              Next · 14:00
            </p>
            <h2 className="mt-1 text-2xl font-semibold text-slate-900">
              {hcp?.full_name ?? 'Loading...'}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              {hcp ? `${hcp.title} · ${hcp.affiliation.trust}, ${hcp.affiliation.site}` : ''}
            </p>
          </div>
          <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
            {hcp?.subspecialty ?? ''}
          </span>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-6 text-sm">
          <div>
            <dt className="text-xs font-medium uppercase tracking-widest text-slate-500">
              Topic
            </dt>
            <dd className="mt-1 text-slate-900">{hcp?.next_call.topic ?? ''}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-widest text-slate-500">
              Location
            </dt>
            <dd className="mt-1 text-slate-900">{hcp?.next_call.location ?? ''}</dd>
          </div>
        </dl>

        <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-4">
          <p className="text-xs text-slate-500">
            Consent on file ·{' '}
            {hcp?.consent.consent_recorded_at
              ? new Date(hcp.consent.consent_recorded_at).toLocaleDateString('en-GB')
              : ''}
          </p>
          <button
            onClick={onStartPrep}
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
          >
            Prep for call →
          </button>
        </div>
      </section>

      <p className="mt-8 text-center text-xs text-slate-400">
        Voice-first prep · silent in-call notetaker · CRM-ready wrap
      </p>
    </div>
  );
}
