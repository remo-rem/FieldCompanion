import { type ComponentProps } from 'react';
import { Room } from 'livekit-client';
import { useEnsureRoom, useStartAudio } from '@livekit/components-react';
import { Button } from '@/components/ui/button';

interface Props extends ComponentProps<'button'> {
  label: string;
  room?: Room;
}

export function StartAudioButton({ label, room, ...props }: Props) {
  const roomEnsured = useEnsureRoom(room);
  const { mergedProps } = useStartAudio({ room: roomEnsured, props });

  return (
    <Button {...props} {...mergedProps}>
      {label}
    </Button>
  );
}
