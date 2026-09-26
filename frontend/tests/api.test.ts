import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, request, setCsrf, streamAnswer } from "@/services/api";

afterEach(() => { vi.unstubAllGlobals(); setCsrf(""); });

function streamResponse(parts: string[]) {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) { parts.forEach(part => controller.enqueue(encoder.encode(part))); controller.close(); },
  }), { headers: { "Content-Type": "text/event-stream" } });
}

describe("HTTP client", () => {
  it("sends the session CSRF token and accepts empty success responses", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetcher);
    setCsrf("session-csrf");
    await expect(request("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
    expect(fetcher).toHaveBeenCalledWith("/api/v1/auth/logout", expect.objectContaining({ credentials: "include", headers: { "X-CSRF-Token": "session-csrf" } }));
  });

  it("announces session expiration and preserves structured API errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ error: { code: "session_expired", message: "Sign in again." } }, { status: 401 })));
    const expired = vi.fn();
    window.addEventListener("session-expired", expired);
    try {
      await expect(request("/auth/session")).rejects.toEqual(new ApiError(401, "session_expired", "Sign in again."));
      expect(expired).toHaveBeenCalledOnce();
    } finally { window.removeEventListener("session-expired", expired); }
  });
});

describe("answer stream", () => {
  it("assembles fragmented SSE frames and accepts validated final content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(streamResponse([
      'event: del', 'ta\ndata: {"text":"Evidence"}\n', '\nevent: done\ndata: {"content":"Evidence [1]","citations":[]}\n\n',
    ])));
    const events = vi.fn();
    await streamAnswer("chat", "Question", new AbortController().signal, events);
    expect(events.mock.calls.map(([event]) => event)).toEqual([
      { type: "delta", text: "Evidence" }, { type: "done", content: "Evidence [1]", citations: [] },
    ]);
  });

  it("reports truncated streams instead of treating partial text as a completed answer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(streamResponse(['event: delta\ndata: {"text":"Partial"}\n\n'])));
    await expect(streamAnswer("chat", "Question", new AbortController().signal, vi.fn())).rejects.toThrow("connection closed");
  });

  it("surfaces provider failures received inside a successful HTTP response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(streamResponse(['event: error\ndata: {"message":"Please retry."}\n\n'])));
    await expect(streamAnswer("chat", "Question", new AbortController().signal, vi.fn())).rejects.toThrow("Please retry.");
  });
});
