import { NextRequest, NextResponse } from 'next/server';
import { AccessToken, type AccessTokenOptions, type VideoGrant } from 'livekit-server-sdk';
import { RoomAgentDispatch, RoomConfiguration } from '@livekit/protocol';

type ConnectionDetails = {
  serverUrl: string;
  roomName: string;
  participantName: string;
  participantToken: string;
  sessionId: string;
};

const API_KEY = process.env.LIVEKIT_API_KEY;
const API_SECRET = process.env.LIVEKIT_API_SECRET;
const LIVEKIT_URL = process.env.LIVEKIT_URL;
const AGENT_NAME = process.env.AGENT_NAME || 'my-agent';

const COOKIE_NAME = 'lk_mongo_user_cookie';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
const IS_PRODUCTION = process.env.NODE_ENV === 'production';

export const revalidate = 0;

type TokenRequestBody = {
  mode?: 'pre_call' | 'in_call' | 'post_call';
  hcp_id?: string;
  session_id?: string;
};

export async function POST(req: NextRequest) {
  if (process.env.NODE_ENV !== 'development') {
    throw new Error(
      'THIS API ROUTE IS INSECURE. DO NOT USE THIS ROUTE IN PRODUCTION WITHOUT AN AUTHENTICATION LAYER.'
    );
  }

  try {
    if (!LIVEKIT_URL) throw new Error('LIVEKIT_URL is not defined');
    if (!API_KEY) throw new Error('LIVEKIT_API_KEY is not defined');
    if (!API_SECRET) throw new Error('LIVEKIT_API_SECRET is not defined');

    const body = (await req.json().catch(() => ({}))) as TokenRequestBody;
    const mode = body.mode ?? 'pre_call';
    const hcpId = body.hcp_id ?? 'hcp_rose';
    const sessionId = body.session_id ?? `session_${Date.now()}_${Math.floor(Math.random() * 10_000)}`;

    let userId = req.cookies.get(COOKIE_NAME)?.value;
    const isNewCookie = !userId;
    if (!userId) {
      userId = crypto.randomUUID();
    }

    const metadata = JSON.stringify({
      user_id: userId,
      tenant_id: 'default',
      mode,
      hcp_id: hcpId,
      session_id: sessionId,
    });

    const roomConfig = new RoomConfiguration({
      agents: [new RoomAgentDispatch({ agentName: AGENT_NAME, metadata })],
    });

    const participantName = 'rep';
    const participantIdentity = `rep_${Math.floor(Math.random() * 10_000)}`;
    const roomName = `${sessionId}_${mode}`;

    const participantToken = await createParticipantToken(
      { identity: participantIdentity, name: participantName },
      roomName,
      roomConfig
    );

    const data: ConnectionDetails = {
      serverUrl: LIVEKIT_URL,
      roomName,
      participantName,
      participantToken,
      sessionId,
    };
    const res = NextResponse.json(data);
    res.headers.set('Cache-Control', 'no-store');
    if (isNewCookie) {
      res.cookies.set({
        name: COOKIE_NAME,
        value: userId,
        httpOnly: true,
        sameSite: 'lax',
        secure: IS_PRODUCTION,
        path: '/',
        maxAge: COOKIE_MAX_AGE,
      });
    }
    return res;
  } catch (error) {
    if (error instanceof Error) {
      console.error(error);
      return new NextResponse(error.message, { status: 500 });
    }
  }
}

function createParticipantToken(
  userInfo: AccessTokenOptions,
  roomName: string,
  roomConfig: RoomConfiguration | undefined
): Promise<string> {
  const at = new AccessToken(API_KEY, API_SECRET, {
    ...userInfo,
    ttl: '15m',
  });
  const grant: VideoGrant = {
    room: roomName,
    roomJoin: true,
    canPublish: true,
    canPublishData: true,
    canSubscribe: true,
  };
  at.addGrant(grant);
  if (roomConfig) {
    at.roomConfig = roomConfig;
  }
  return at.toJwt();
}