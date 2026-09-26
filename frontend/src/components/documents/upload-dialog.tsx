"use client";
import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileText, UploadCloud } from "lucide-react";
import { Button, Dialog } from "@/components/ui/primitives";
import { uploadDocument } from "@/services/api";
import { useWorkspace } from "@/providers/workspace";
import { cn, errorMessage } from "@/lib/utils";

interface UploadItem { id: string; file: File; progress: number; status: "uploading" | "done" | "error"; error?: string }
export function UploadDialog({ open, onOpenChange, collection }: { open: boolean; onOpenChange: (open: boolean) => void; collection?: string }) {
  const { workspace } = useWorkspace(); const client = useQueryClient(); const input = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<UploadItem[]>([]); const [dragging, setDragging] = useState(false);
  function update(id: string, patch: Partial<UploadItem>) { setItems(current => current.map(item => item.id === id ? { ...item, ...patch } : item)); }
  async function upload(item: UploadItem) {
    if (!/\.(pdf|docx|txt|md)$/i.test(item.file.name)) { update(item.id, { status: "error", error: "Choose a PDF, DOCX, TXT, or Markdown file." }); return; }
    if (!item.file.size || item.file.size > 25 * 1024 * 1024) { update(item.id, { status: "error", error: "Choose a nonempty file up to 25 MB." }); return; }
    update(item.id, { status: "uploading", error: undefined, progress: 0 });
    try { await uploadDocument(workspace.id, item.file, progress => update(item.id, { progress }), collection); update(item.id, { status: "done", progress: 100 }); await client.invalidateQueries({ queryKey: ["documents", workspace.id] }); await client.invalidateQueries({ queryKey: ["stats", workspace.id] }); } catch (error) { update(item.id, { status: "error", error: errorMessage(error) }); }
  }
  async function add(files: FileList | File[]) { const batch = Array.from(files).slice(0, 20).map(file => ({ id: crypto.randomUUID(), file, progress: 0, status: "uploading" as const })); setItems(current => [...current, ...batch]); for (const item of batch) await upload(item); }
  return <Dialog open={open} onOpenChange={value => { if (!items.some(item => item.status === "uploading")) onOpenChange(value); }} title="Add to your knowledge" description="Upload PDF, Word, Markdown, or text files. We’ll extract and index their content in the background."><div className={cn("upload-zone", dragging && "dragging")} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); void add(event.dataTransfer.files); }}><UploadCloud size={30} strokeWidth={1.5} /><h3>Drop your documents here</h3><p>Up to 25 MB per file · 20 files at a time</p><input ref={input} id="document-upload" type="file" aria-label="Select documents" multiple accept=".pdf,.docx,.txt,.md" onChange={event => { if (event.target.files) void add(event.target.files); event.target.value = ""; }} /><Button variant="secondary" onClick={() => input.current?.click()}>Browse files</Button></div><div className="upload-list" aria-live="polite">{items.map(item => <div className="upload-item" key={item.id}><div className="row"><FileText size={17} /><span className="document-name" style={{ flex: 1 }}>{item.file.name}</span>{item.status === "done" ? <CheckCircle2 size={17} style={{ color: "var(--green)" }} /> : item.status === "uploading" ? <span className="small muted">{item.progress}%</span> : <Button variant="ghost" onClick={() => void upload(item)}>Retry</Button>}</div>{item.status === "uploading" && <div className="progress-track" role="progressbar" aria-label={`Uploading ${item.file.name}`} aria-valuenow={item.progress} aria-valuemin={0} aria-valuemax={100}><div className="progress-fill" style={{ width: `${item.progress}%` }} /></div>}{item.status === "done" && <p className="small muted" style={{ marginTop: 6 }}>Uploaded. Processing will continue in the background.</p>}{item.error && <p className="field-error" role="alert">{item.error}</p>}</div>)}</div><div className="dialog-actions"><Button variant="secondary" disabled={items.some(item => item.status === "uploading")} onClick={() => onOpenChange(false)}>Done</Button></div></Dialog>;
}
