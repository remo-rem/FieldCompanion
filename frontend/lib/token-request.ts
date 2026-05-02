// Module-level holder backing TokenSource.custom. The livekit-client
// TokenSource.endpoint helper drops the request body, so we keep the
// per-mode payload here and read it from the custom fetcher in app.tsx.
export type TokenRequest = {
  mode: 'pre_call' | 'in_call' | 'post_call';
  hcp_id: string;
  session_id: string;
};

let current: TokenRequest = {
  mode: 'pre_call',
  hcp_id: 'hcp_rose',
  session_id: `session_${Date.now()}_init`,
};

export function setTokenRequest(req: TokenRequest): void {
  current = req;
}

export function getTokenRequest(): TokenRequest {
  return current;
}
