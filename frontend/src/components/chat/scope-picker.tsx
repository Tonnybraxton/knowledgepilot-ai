"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useWorkspace } from "@/providers/workspace";
import { ErrorState, Pagination } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/utils";
import { useState } from "react";
import type { Scope } from "@/types/api";

export function ScopePicker({ value, onChange, disabled }: { value: Scope; onChange: (scope: Scope) => void; disabled?: boolean }) {
  const { workspace } = useWorkspace();
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const collections = useQuery({ queryKey: ["collections", workspace.id], queryFn: () => api.collections(workspace.id) });
  const params = new URLSearchParams({ status: "ready", page: String(page), q: query, ...(value.collection_id ? { collection_id: value.collection_id } : {}) });
  const documents = useQuery({ queryKey: ["documents", workspace.id, params.toString()], queryFn: () => api.documents(workspace.id, params.toString()) });
  const selected = value.document_ids ?? [];
  return <details className="scope-picker"><summary>Sources: {selected.length ? `${selected.length} selected documents` : value.collection_id ? "Selected collection" : "All workspace documents"}</summary><fieldset disabled={disabled} className="stack"><legend className="sr-only">Select knowledge sources</legend><div className="field"><label htmlFor="scope-collection">Collection</label><select id="scope-collection" value={value.collection_id ?? ""} onChange={event => { onChange({ collection_id: event.target.value || null, document_ids: [] }); setPage(1); }}><option value="">All collections</option>{collections.data?.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div><div className="field"><label htmlFor="scope-filter">Find indexed documents</label><input id="scope-filter" value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} /></div><p className="small muted">Select up to 20 documents, or leave all unchecked to use every indexed document in this scope.</p>{(collections.error || documents.error) && <ErrorState message={errorMessage(collections.error ?? documents.error)} />}{documents.isPending ? <p role="status">Loading documents…</p> : documents.data?.items.map(item => <label className="row" key={item.id}><input type="checkbox" checked={selected.includes(item.id)} disabled={!selected.includes(item.id) && selected.length >= 20} onChange={event => onChange({ ...value, document_ids: event.target.checked ? [...selected, item.id] : selected.filter(id => id !== item.id) })} />{item.filename}</label>)}{documents.data?.total === 0 && <p className="muted">No indexed documents in this scope yet.</p>}{documents.data && <Pagination page={page} total={documents.data.total} pageSize={20} onChange={setPage} />}</fieldset></details>;
}
