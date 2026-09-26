"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { MessageSquare } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/services/api";
import { useWorkspace } from "@/providers/workspace";
import { date, errorMessage } from "@/lib/utils";
import { Button, Dialog, EmptyState, ErrorState, Pagination, Skeleton } from "@/components/ui/primitives";
import type { Conversation } from "@/types/api";

export function Conversations() {
  const { workspace } = useWorkspace(); const client = useQueryClient(); const [q, setQ] = useState(""); const [page, setPage] = useState(1); const [target, setTarget] = useState<Conversation | null>(null); const [busy, setBusy] = useState(false);
  const query = useQuery({ queryKey: ["conversations", workspace.id, q, page], queryFn: () => api.conversations(workspace.id, new URLSearchParams({ q, page: String(page) }).toString()) });
  async function remove() { if (!target) return; setBusy(true); try { await api.deleteConversation(target.id); await client.invalidateQueries({ queryKey: ["conversations", workspace.id] }); setTarget(null); } catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); } }
  return <div className="stack"><div className="page-heading"><div><h1>Your conversations</h1><p>Return to a question and pick up where you left off.</p></div><Link className="button button-primary" href="/app/chat">New conversation</Link></div><input aria-label="Search conversations" placeholder="Search titles and messages…" value={q} onChange={event => { setQ(event.target.value); setPage(1); }} />{query.isPending ? <Skeleton /> : query.error ? <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} /> : query.data?.items.length ? <div className="card">{query.data.items.map(item => <div className="list-item row between" key={item.id}><Link href={`/app/chat/${item.id}`}><h2>{item.title}</h2><p className="small muted">{date(item.updated_at)}</p></Link><Button variant="ghost" aria-label={`Delete ${item.title}`} onClick={() => setTarget(item)}>Delete</Button></div>)}</div> : <EmptyState icon={<MessageSquare />} title={q ? "No matching conversations" : "Start exploring your knowledge"} description="Ask a question and your conversation will be saved here." />}{query.data && <Pagination page={page} total={query.data.total} pageSize={20} onChange={setPage} />}<Dialog open={!!target} onOpenChange={open => { if (!open) setTarget(null); }} title="Delete conversation?" description="This permanently deletes its messages and saved citations."><p>{target?.title}</p><div className="dialog-actions"><Button variant="secondary" onClick={() => setTarget(null)}>Cancel</Button><Button variant="danger" busy={busy} onClick={() => void remove()}>Delete conversation</Button></div></Dialog></div>;
}
