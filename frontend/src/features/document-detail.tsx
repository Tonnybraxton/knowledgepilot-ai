"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";
import { api } from "@/services/api";
import { bytes, date, errorMessage } from "@/lib/utils";
import { Button, EmptyState, ErrorState, Pagination, Skeleton } from "@/components/ui/primitives";
import { StatusBadge } from "@/components/documents/document-table";
import { FileText } from "lucide-react";

export function DocumentDetail({ id, chunk }: { id: string; chunk?: string }) {
  const [page, setPage] = useState(1); const [busy, setBusy] = useState(false); const client = useQueryClient();
  const document = useQuery({ queryKey: ["document", id], queryFn: () => api.document(id), refetchInterval: query => query.state.data && !["ready", "failed"].includes(query.state.data.status) ? 2000 : false });
  const passages = useQuery({ queryKey: ["chunks", id, page, chunk], queryFn: () => api.chunks(id, new URLSearchParams({ page: String(page), ...(chunk ? { chunk_id: chunk } : {}) }).toString()), enabled: document.data?.status === "ready" });
  async function reprocess() { setBusy(true); try { await api.reprocess(id); await client.invalidateQueries({ queryKey: ["document", id] }); } catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); } }
  if (document.isPending) return <Skeleton />;
  if (document.error || !document.data) return <ErrorState message={errorMessage(document.error)} retry={() => void document.refetch()} />;
  const item = document.data;
  return <div className="stack"><Link href="/app/documents" className="text-link">← Documents</Link><div className="page-heading"><div><h1>{item.filename}</h1><p>{bytes(item.size_bytes)} · Added {date(item.created_at)} · {item.chunk_count} indexed passages</p></div><a className="button button-secondary" href={`/api/v1/documents/${id}/source`}>Download original</a></div><div className="row wrap"><StatusBadge status={item.status} />{["failed", "ready"].includes(item.status) && <Button variant="secondary" busy={busy} onClick={() => void reprocess()}>Reprocess document</Button>}</div>{item.processing_error && <ErrorState message={item.processing_error} />}{!['ready', 'failed'].includes(item.status) && <p role="status">Your document is being processed. This page updates automatically.</p>}{passages.error && <ErrorState message={errorMessage(passages.error)} retry={() => void passages.refetch()} />}{passages.data?.items.map(passage => <article className="card card-body stack" id={`chunk-${passage.id}`} key={passage.id}><h2>{passage.page_number ? `Page ${passage.page_number}` : passage.section_title ?? `Passage ${passage.chunk_index + 1}`}</h2><p className="source-excerpt">{passage.content}</p></article>)}{passages.data && <Pagination page={passages.data.page} total={passages.data.total} pageSize={passages.data.page_size} onChange={setPage} />}{passages.data?.items.length === 0 && <EmptyState icon={<FileText />} title="No passages available" description="Reprocess this document to rebuild its searchable content." />}</div>;
}

