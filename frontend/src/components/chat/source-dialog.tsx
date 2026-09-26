"use client";
import Link from "next/link";
import { Dialog } from "@/components/ui/primitives";
import type { Citation } from "@/types/api";

export function SourceDialog({ source, onClose }: { source: Citation | null; onClose: () => void }) {
  return <Dialog open={!!source} onOpenChange={open => { if (!open) onClose(); }} title={source?.document_name ?? "Source passage"} description="The passage retrieved for this answer.">
    {source && <div className="stack"><p className="small muted">Source [{source.citation_number}]{source.page_number ? ` · Page ${source.page_number}` : ""}{source.section_title ? ` · ${source.section_title}` : ""}</p><blockquote className="source-excerpt">{source.excerpt}</blockquote>{source.document_id ? <div className="row wrap"><Link className="button button-secondary" href={`/app/documents/${source.document_id}${source.chunk_id ? `?chunk=${source.chunk_id}` : ""}`}>Inspect document</Link><a className="button button-primary" href={`/api/v1/documents/${source.document_id}/source`}>Download original</a></div> : <p role="status" className="muted">This document has been deleted. The excerpt is preserved as part of your conversation.</p>}</div>}
  </Dialog>;
}
