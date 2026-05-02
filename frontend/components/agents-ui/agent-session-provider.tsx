import {
  RoomAudioRenderer,
  SessionProvider,
  type SessionProviderProps,
  type UseSessionReturn,
} from '@livekit/components-react';

interface Props extends SessionProviderProps {
  session: UseSessionReturn;
  children: React.ReactNode;
}

export function AgentSessionProvider({ session, children }: Props) {
  return (
    <SessionProvider session={session}>
      {children}
      <RoomAudioRenderer />
    </SessionProvider>
  );
}
