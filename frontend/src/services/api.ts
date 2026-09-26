import type { Collection, Conversation, Document, Page, Scope, SearchHit, Session, Stats, Workspace, Message, Chunk, User, Citation } from "@/types/api";

let csrfToken = "";
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
export function setCsrf(token: string) { csrfToken = token; }
async function decodeError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null);
  if (response.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event("session-expired"));
  return new ApiError(response.status, body?.error?.code ?? "network", body?.error?.message ?? `Request failed (${response.status}). Please retry.`);
}
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...options, credentials: "include", headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), "X-CSRF-Token": csrfToken, ...options.headers } });
  if (!response.ok) throw await decodeError(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
const json = (data: unknown) => JSON.stringify(data);
export const api = {
  session: () => request<Session>("/auth/session"),
  login: (data: { email: string; password: string }) => request<Session>("/auth/login", { method: "POST", body: json(data) }),
  register: (data: { email: string; password: string; display_name: string }) => request<Session>("/auth/register", { method: "POST", body: json(data) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  forgot: (email: string) => request<{ message: string }>("/auth/forgot-password", { method: "POST", body: json({ email }) }),
  reset: (token: string, password: string) => request<void>("/auth/reset-password", { method: "POST", body: json({ token, password }) }),
  profile: (display_name: string, theme: string) => request<User>("/users/me", { method: "PATCH", body: json({ display_name, theme }) }),
  workspaces: () => request<Workspace[]>("/workspaces"),
  createWorkspace: (name: string) => request<Workspace>("/workspaces", { method: "POST", body: json({ name }) }),
  stats: (id: string) => request<Stats>(`/workspaces/${id}/stats`),
  documents: (id: string, query = "") => request<Page<Document>>(`/workspaces/${id}/documents?${query}`),
  document: (id: string) => request<Document>(`/documents/${id}`),
  chunks: (id: string, query = "") => request<Page<Chunk>>(`/documents/${id}/chunks?${query}`),
  updateDocument: (id: string, data: { filename?: string; collection_id?: string | null }) => request<Document>(`/documents/${id}`, { method: "PATCH", body: json(data) }),
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  reprocess: (id: string) => request<Document>(`/documents/${id}/processing-jobs`, { method: "POST" }),
  collections: (id: string) => request<Page<Collection>>(`/workspaces/${id}/collections?page_size=100`),
  createCollection: (id: string, name: string, description: string) => request<Collection>(`/workspaces/${id}/collections`, { method: "POST", body: json({ name, description }) }),
  updateCollection: (id: string, name: string, description: string) => request<Collection>(`/collections/${id}`, { method: "PATCH", body: json({ name, description }) }),
  deleteCollection: (id: string) => request<void>(`/collections/${id}`, { method: "DELETE" }),
  conversations: (id: string, query = "") => request<Page<Conversation>>(`/workspaces/${id}/conversations?${query}`),
  createConversation: (id: string, scope: Scope, title?: string) => request<Conversation>(`/workspaces/${id}/conversations`, { method: "POST", body: json({ scope, ...(title ? { title } : {}) }) }),
  conversation: (id: string) => request<Conversation>(`/conversations/${id}`),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
  messages: (id: string, page = 1) => request<Page<Message>>(`/conversations/${id}/messages?page=${page}`),
  search: (id: string, query: string, mode: string, scope: Scope, mime_type?: string) => request<SearchHit[]>(`/workspaces/${id}/search`, { method: "POST", body: json({ query, mode, scope, mime_type }) }),
};

export function uploadDocument(workspace: string, file: File, onProgress: (percent: number) => void, collection?: string): Promise<Document> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/v1/workspaces/${workspace}/documents`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-CSRF-Token", csrfToken);
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100)); };
    xhr.onerror = () => reject(new Error("Upload interrupted. Check your connection and retry."));
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(body as Document);
        else reject(new ApiError(xhr.status, body.error?.code ?? "upload", body.error?.message ?? "Upload failed."));
      } catch { reject(new Error("The upload server returned an invalid response.")); }
    };
    const form = new FormData(); form.append("file", file); if (collection) form.append("collection_id", collection); xhr.send(form);
  });
}

export interface StreamEvent { type: string; text?: string; message?: string; content?: string; id?: string; citations?: Citation[]; status?: string }
export async function streamAnswer(id: string, content: string, signal: AbortSignal, onEvent: (event: StreamEvent) => void, regenerate = false) {
  const response = await fetch(`/api/v1/conversations/${id}/messages`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken }, body: json({ content, regenerate }), signal });
  if (!response.ok) throw await decodeError(response);
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Streaming is unavailable in this browser.");
  const decoder = new TextDecoder(); let buffer = ""; let finished = false;
  try {
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n"); buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const type = frame.split("\n").find(line => line.startsWith("event: "))?.slice(7);
        const data = frame.split("\n").filter(line => line.startsWith("data: ")).map(line => line.slice(6)).join("\n");
        if (type && data) { const parsed = JSON.parse(data); onEvent({ type, ...parsed }); if (type === "done") finished = true; if (type === "error") throw new Error(parsed.message); }
      }
    }
    if (!finished) throw new Error("The connection closed before the answer finished. Your question is saved; retry the response.");
  } finally { await reader.cancel(); reader.releaseLock(); }
}
