import type { 
  ChatSummary, 
  ApprovalRecord, 
  LearningCandidate, 
  CharacterProfile 
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(
  url: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(url, {
    ...(init ?? {}),
    headers: {
      ...(init?.headers ?? {}),
      Authorization: `Bearer ${token}`,
    },
    credentials: "same-origin",
  });
  if (!res.ok) {
    throw new ApiError(res.status, `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

function splitKey(key: string): { channel: string; chatId: string } {
  const idx = key.indexOf(":");
  if (idx === -1) return { channel: "", chatId: key };
  return { channel: key.slice(0, idx), chatId: key.slice(idx + 1) };
}

export async function listSessions(
  token: string,
  base: string = "",
): Promise<ChatSummary[]> {
  type Row = {
    key: string;
    created_at: string | null;
    updated_at: string | null;
    preview?: string;
  };
  const body = await request<{ sessions: Row[] }>(
    `${base}/api/sessions`,
    token,
  );
  return body.sessions.map((s) => ({
    key: s.key,
    ...splitKey(s.key),
    createdAt: s.created_at,
    updatedAt: s.updated_at,
    preview: s.preview ?? "",
  }));
}

/** Signed image URL attached to a historical user message. The server
 * emits these in place of raw on-disk paths so the client can render
 * previews without learning where media lives on disk. Each URL is a
 * self-authenticating ``/api/media/...`` route (see backend
 * ``_sign_media_path``) safe to drop into an ``<img src>`` attribute. */
export interface SessionMediaUrl {
  url: string;
  name?: string;
}

export async function fetchSessionMessages(
  token: string,
  key: string,
  base: string = "",
): Promise<{
  key: string;
  created_at: string | null;
  updated_at: string | null;
  messages: Array<{
    role: string;
    content: string;
    timestamp?: string;
    tool_calls?: unknown;
    tool_call_id?: string;
    name?: string;
    /** Present on ``user`` turns that attached images. Paths have already
     * been stripped server-side; only the signed fetch URLs survive. */
    media_urls?: SessionMediaUrl[];
  }>;
}> {
  return request(
    `${base}/api/sessions/${encodeURIComponent(key)}/messages`,
    token,
  );
}
export async function deleteSession(
  token: string,
  key: string,
  base: string = "",
): Promise<boolean> {
  const body = await request<{ deleted: boolean }>(
    `${base}/api/sessions/${encodeURIComponent(key)}/delete`,
    token,
    { method: "POST" },
  );
  return body.deleted;
}

export async function listApprovals(
  token: string,
  base: string = "",
): Promise<ApprovalRecord[]> {
  const body = await request<{ approvals: ApprovalRecord[] }>(
    `${base}/api/approvals`,
    token,
  );
  return body.approvals;
}


export async function handleApproval(
  token: string,
  id: string,
  action: "approve" | "deny",
  base: string = "",
): Promise<void> {
  await request(
    `${base}/api/approvals/${id}/${action}`,
    token,
    { method: "POST" }
  );
}

export async function listLearning(
  token: string,
  base: string = "",
): Promise<LearningCandidate[]> {
  const body = await request<{ candidates: LearningCandidate[] }>(
    `${base}/api/learning`,
    token,
  );
  return body.candidates;
}

export async function handleLearning(
  token: string,
  id: string,
  action: "apply" | "reject",
  base: string = "",
): Promise<void> {
  await request(
    `${base}/api/learning/${id}/${action}`,
    token,
    { method: "POST" }
  );
}

export async function listProfiles(
  token: string,
  base: string = "",
): Promise<CharacterProfile[]> {
  const body = await request<{ profiles: CharacterProfile[] }>(
    `${base}/api/profiles`,
    token,
  );
  return body.profiles;
}

