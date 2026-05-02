'use client';

import { useState } from 'react';
import { useSessionContext } from '@livekit/components-react';
import { CallView } from '@/components/app/views/call-view';
import { DashboardView } from '@/components/app/views/dashboard-view';
import { PrepView } from '@/components/app/views/prep-view';
import { WrapView } from '@/components/app/views/wrap-view';
import { setTokenRequest } from '@/lib/token-request';

type View = 'dashboard' | 'prep' | 'call' | 'wrap';
type Mode = 'pre_call' | 'in_call' | 'post_call';

export function ViewController() {
  const [view, setView] = useState<View>('dashboard');
  const [sessionId, setSessionId] = useState<string>(() => `session_${Date.now()}`);
  const { isConnected, start, end } = useSessionContext();

  const startMode = async (mode: Mode) => {
    if (isConnected) {
      await end();
    }
    setTokenRequest({ mode, hcp_id: 'hcp_rose', session_id: sessionId });
    await start();
  };

  const goToPrep = async () => {
    setView('prep');
    await startMode('pre_call');
  };

  const goToCall = async () => {
    setView('call');
    await startMode('in_call');
  };

  const goToWrap = async () => {
    setView('wrap');
    await startMode('post_call');
  };

  const goToDashboard = async () => {
    if (isConnected) {
      await end();
    }
    setSessionId(`session_${Date.now()}`);
    setView('dashboard');
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {view === 'dashboard' && <DashboardView onStartPrep={goToPrep} />}
      {view === 'prep' && <PrepView sessionId={sessionId} onStartCall={goToCall} />}
      {view === 'call' && <CallView sessionId={sessionId} onEndCall={goToWrap} />}
      {view === 'wrap' && <WrapView sessionId={sessionId} onApprove={goToDashboard} />}
    </div>
  );
}
