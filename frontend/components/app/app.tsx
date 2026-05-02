'use client';

import { useMemo } from 'react';
import { TokenSource } from 'livekit-client';
import { useSession } from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react/dist/ssr';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/ui/sonner';
import { useAgentErrors } from '@/hooks/useAgentErrors';
import { getTokenRequest } from '@/lib/token-request';

function AppInner() {
  useAgentErrors();
  return (
    <main className="grid h-svh grid-cols-1 place-content-center">
      <ViewController />
    </main>
  );
}

export function App() {
  const tokenSource = useMemo(
    () =>
      TokenSource.custom(async () => {
        const response = await fetch('/api/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(getTokenRequest()),
        });
        if (!response.ok) {
          throw new Error(`Token fetch failed: ${response.status}`);
        }
        return response.json();
      }),
    []
  );

  const session = useSession(tokenSource);

  return (
    <AgentSessionProvider session={session}>
      <AppInner />
      <StartAudioButton label="Start Audio" />
      <Toaster icons={{ warning: <WarningIcon weight="bold" /> }} position="top-center" />
    </AgentSessionProvider>
  );
}
