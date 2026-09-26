"use client";
import { useQuery } from "@tanstack/react-query";
import { FileText, Search, Upload } from "lucide-react";
import { useState } from "react";
import { useWorkspace } from "@/providers/workspace";
import { api } from "@/services/api";
import { errorMessage } from "@/lib/utils";
import { Button, EmptyState, ErrorState, Pagination, Skeleton } from "@/components/ui/primitives";
import { DocumentTable } from "@/components/documents/document-table";
import { UploadDialog } from "@/components/documents/upload-dialog";
export function Documents({ collection }: { collection?: string }) {
  const { workspace } = useWorkspace(); const [uploading, setUploading] = useState(false); const [q, setQ] = useState(""); const [status, setStatus] = useState(""); const [sort, setSort] = useState("newest"); const [page, setPage] = useState(1);
  const params = new URLSearchParams({ q, page: String(page), sort, ...(status ? { status } : {}), ...(collection ? { collection_id: collection } : {}) });
  const documents = useQuery({ queryKey: ["documents", workspace.id, params.toString()], queryFn: () => api.documents(workspace.id, params.toString()), refetchInterval: query => query.state.data?.items.some(item => !["ready", "failed"].includes(item.status)) ? 3000 : false });
  const collections = useQuery({ queryKey: ["collections", workspace.id], queryFn: () => api.collections(workspace.id), enabled: !!collection });
  const title = collection ? collections.data?.items.find(item => item.id === collection)?.name ?? "Collection documents" : "Your documents";
  return <><div className="page-heading"><div><h1>{title}</h1><p>A library of everything you want to understand better.</p></div><Button onClick={() => setUploading(true)}><Upload size={16} />Upload documents</Button></div><div className="toolbar"><div className="search-input"><Search size={16} /><input aria-label="Search documents" placeholder="Find a document…" value={q} onChange={event => { setQ(event.target.value); setPage(1); }} /></div><select aria-label="Filter by processing status" value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}><option value="">All statuses</option>{["ready", "queued", "extracting", "chunking", "embedding", "indexing", "failed"].map(value => <option key={value}>{value}</option>)}</select><select aria-label="Sort documents" value={sort} onChange={event => setSort(event.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="name">Name A–Z</option></select><span className="small muted" style={{ marginLeft: "auto" }}>{documents.data?.total ?? "—"} documents</span></div>{documents.isPending ? <Skeleton rows={5} /> : documents.error ? <ErrorState message={errorMessage(documents.error)} retry={() => void documents.refetch()} /> : documents.data?.items.length ? <><div className="card"><DocumentTable documents={documents.data.items} /></div><Pagination page={page} total={documents.data.total} pageSize={20} onChange={setPage} /></> : <div className="card"><EmptyState icon={<FileText size={26} />} title={q || status ? "No documents match" : "Build your knowledge library"} description={q || status ? "Try a different search or remove a status filter." : "Upload your first document to start building your knowledge base."}><Button variant="secondary" onClick={() => setUploading(true)}>Upload a document</Button></EmptyState></div>}<UploadDialog open={uploading} onOpenChange={setUploading} collection={collection} /></>;
}
