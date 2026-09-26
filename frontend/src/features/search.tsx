"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Search as SearchIcon } from "lucide-react";
import { api } from "@/services/api";
import { useWorkspace } from "@/providers/workspace";
import { Button, EmptyState, ErrorState } from "@/components/ui/primitives";
import { ScopePicker } from "@/components/chat/scope-picker";
import { SourceDialog } from "@/components/chat/source-dialog";
import { errorMessage } from "@/lib/utils";
import type { Citation, Scope } from "@/types/api";

const schema = z.object({ query: z.string().trim().min(1, "Enter a search term.").max(2000), mode: z.enum(["hybrid", "semantic", "keyword"]), mime: z.string() });
export function KnowledgeSearch() {
  const { workspace } = useWorkspace(); const [scope, setScope] = useState<Scope>({}); const [source, setSource] = useState<Citation | null>(null);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { query: "", mode: "hybrid", mime: "" } });
  const search = useMutation({ mutationFn: (data: z.infer<typeof schema>) => api.search(workspace.id, data.query, data.mode, scope, data.mime || undefined) });
  return <div className="stack"><div className="page-heading"><div><h1>Find the passage you need</h1><p>Search by meaning, exact terms, or both.</p></div></div><form onSubmit={form.handleSubmit(data => search.mutate(data))} className="stack"><div className="toolbar"><div className="search-input"><SearchIcon size={17} /><input aria-label="Search knowledge" placeholder="Search across your knowledge…" {...form.register("query")} /></div><select aria-label="Search mode" {...form.register("mode")}><option value="hybrid">Hybrid search</option><option value="semantic">Semantic search</option><option value="keyword">Keyword search</option></select><select aria-label="File type" {...form.register("mime")}><option value="">All file types</option><option value="application/pdf">PDF</option><option value="application/vnd.openxmlformats-officedocument.wordprocessingml.document">Word</option><option value="text/plain">Text</option><option value="text/markdown">Markdown</option></select><Button type="submit" busy={search.isPending}>Search</Button></div>{form.formState.errors.query && <p className="field-error" role="alert">{form.formState.errors.query.message}</p>}<ScopePicker value={scope} onChange={setScope} /></form>{search.error && <ErrorState message={errorMessage(search.error)} />}{search.isPending && <p role="status">Searching your documents…</p>}{search.data?.map((hit, index) => <article className="card card-body stack" key={hit.chunk_id}><div><button className="text-link" onClick={() => setSource({ ...hit, citation_number: index + 1, excerpt: hit.content })}>{hit.document_name}</button><p className="small muted">{hit.page_number ? `Page ${hit.page_number}` : hit.section_title ?? "Document passage"}</p></div><p className="source-excerpt">{hit.content}</p><Button variant="secondary" onClick={() => setSource({ ...hit, citation_number: index + 1, excerpt: hit.content })}>Inspect source</Button></article>)}{search.data?.length === 0 && <EmptyState icon={<SearchIcon />} title="No matching passages" description="Try different terms, broaden your sources, or check whether your documents have finished processing." />}{search.isIdle && <EmptyState icon={<SearchIcon />} title="Your next insight starts here" description="Search indexed documents and inspect the original evidence behind each result." />}<SourceDialog source={source} onClose={() => setSource(null)} /></div>;
}
