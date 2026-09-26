"use client";
import { useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Copy, Send, Square, RefreshCw, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { Button, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import { SourceDialog } from "@/components/chat/source-dialog";
import { ScopePicker } from "@/components/chat/scope-picker";
import { useWorkspace } from "@/providers/workspace";
import { api, streamAnswer } from "@/services/api";
import { errorMessage } from "@/lib/utils";
import type { Citation, Message, Scope } from "@/types/api";

const schema = z.object({ question: z.string().trim().min(1, "Enter a question.").max(6000, "Keep questions under 6,000 characters.") });
export function Chat({ conversationId }: { conversationId?: string }) {
  const { workspace } = useWorkspace();
  const client = useQueryClient();
  const [activeId, setActiveId] = useState(conversationId);
  const [scope, setScope] = useState<Scope>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [source, setSource] = useState<Citation | null>(null);
  const controller = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { question: "" } });
  const conversation = useQuery({ queryKey: ["conversation", workspace.id, activeId], queryFn: () => api.conversation(activeId!), enabled: !!activeId });
  const history = useInfiniteQuery({ queryKey: ["messages", workspace.id, activeId], queryFn: ({ pageParam }) => api.messages(activeId!, pageParam), initialPageParam: 1, getNextPageParam: last => last.page * last.page_size < last.total ? last.page + 1 : undefined, enabled: !!activeId && !busy });
  const messages = history.data?.pages.toReversed().flatMap(page => page.items) ?? [];
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [draft]);

  async function ask(question: string, regenerate = false) {
    if (controller.current) return;
    const abort = new AbortController(); controller.current = abort;
    setBusy(true); setError(""); setDraft(""); setPendingQuestion(regenerate ? "" : question);
    let id = activeId;
    try {
      if (!id) {
        const created = await api.createConversation(workspace.id, scope);
        id = created.id; setActiveId(id);
        window.history.replaceState(null, "", `/app/chat/${id}`);
      }
      await streamAnswer(id, question, abort.signal, event => {
        if (event.type === "delta") setDraft(current => current + (event.text ?? ""));
        if (event.type === "done") setDraft(event.content ?? "");
      }, regenerate);
      form.reset();
    } catch (cause) {
      if (abort.signal.aborted) setError("Response stopped. You can retry the saved question.");
      else setError(errorMessage(cause));
    } finally {
      if (id) await client.fetchInfiniteQuery({ queryKey: ["messages", workspace.id, id], queryFn: ({ pageParam }) => api.messages(id!, pageParam), initialPageParam: 1 }).catch(() => undefined);
      await client.invalidateQueries({ queryKey: ["conversations", workspace.id] });
      await client.invalidateQueries({ queryKey: ["conversation", workspace.id, id] });
      controller.current = null; setBusy(false); setPendingQuestion(""); setDraft("");
    }
  }
  function renderMessage(message: Message) {
    return <article className={`chat-message ${message.role}`} key={message.id}><div className="eyebrow">{message.role === "user" ? "You" : "KnowledgePilot"}</div><div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{ img: () => null, a: ({ children, href }) => <a href={href} target="_blank" rel="noreferrer">{children}</a> }}>{message.content || (message.status === "failed" ? "The response could not be completed." : "No response text was saved.")}</ReactMarkdown></div>{message.role === "assistant" && <><div className="row wrap source-chips">{message.citations.map(citation => <button className="source-chip" key={citation.citation_number} onClick={() => setSource(citation)}>[{citation.citation_number}] {citation.document_name}{citation.page_number ? ` · p. ${citation.page_number}` : ""}</button>)}</div><div className="row small muted"><span>{message.status === "complete" ? "Check the sources before relying on this answer." : `Response ${message.status}. This text has not been verified.`}</span><Button variant="ghost" aria-label="Copy answer" onClick={async () => { try { await navigator.clipboard.writeText(message.content); toast.success("Answer copied"); } catch { toast.error("Could not access the clipboard."); } }}><Copy size={14} /></Button></div></>}</article>;
  }
  return <div className="chat-layout"><div className="page-heading"><div><h1>{conversation.data?.title ?? "Ask your knowledge"}</h1><p>Follow an idea, with your sources close by.</p></div></div><ScopePicker value={conversation.data?.retrieval_scope ?? scope} onChange={setScope} disabled={busy || !!activeId} />{conversation.error && <ErrorState message={errorMessage(conversation.error)} />}{history.error && <ErrorState message={errorMessage(history.error)} retry={() => void history.refetch()} />}<div className="chat-transcript" aria-label="Conversation">{history.hasNextPage && <Button variant="secondary" busy={history.isFetchingNextPage} onClick={() => void history.fetchNextPage()}>Load earlier messages</Button>}{activeId && history.isPending && !busy ? <Skeleton /> : messages.map(renderMessage)}{!messages.length && !busy && !activeId && <EmptyState icon={<Sparkles size={28} />} title="Start with a question" description="Ask for a summary, compare selected sources, or investigate a specific detail. Answers will cite the passages used." />}{busy && <>{pendingQuestion && <article className="chat-message user"><div className="eyebrow">You</div><p>{pendingQuestion}</p></article>}<article className="chat-message assistant"><div className="eyebrow">KnowledgePilot · generating</div><p className="stream-draft">{draft || "Finding relevant passages…"}</p><p className="small muted">Citation references are checked when the answer finishes.</p></article></>}<div ref={end} /></div>{error && <ErrorState message={error} />}{!busy && messages.some(message => message.role === "user") && <Button variant="ghost" onClick={() => void ask("Regenerate", true)}><RefreshCw size={14} />Retry last answer</Button>}<form className="chat-composer card" onSubmit={event => { void form.handleSubmit(data => ask(data.question))(event); }}><label className="sr-only" htmlFor="question">Your question</label><textarea id="question" rows={3} placeholder="What would you like to understand?" disabled={busy} {...form.register("question")} onKeyDown={event => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void form.handleSubmit(data => ask(data.question))(); } }} />{form.formState.errors.question && <p role="alert" className="field-error">{form.formState.errors.question.message}</p>}<div className="row between"><span className="small muted">Ctrl / ⌘ + Enter to send</span>{busy ? <Button type="button" variant="secondary" onClick={() => controller.current?.abort()}><Square size={15} />Stop response</Button> : <Button type="submit" disabled={!!conversation.error}><Send size={15} />Ask question</Button>}</div></form><SourceDialog source={source} onClose={() => setSource(null)} /></div>;
}

