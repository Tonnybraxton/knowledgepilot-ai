"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { Folder, Plus } from "lucide-react";
import { toast } from "sonner";
import { useWorkspace } from "@/providers/workspace";
import { api } from "@/services/api";
import { errorMessage } from "@/lib/utils";
import { Button, Dialog, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import type { Collection } from "@/types/api";

const schema = z.object({ name: z.string().trim().min(1, "Enter a name.").max(100), description: z.string().max(2000) });
export function Collections() {
  const { workspace } = useWorkspace(); const client = useQueryClient(); const [editing, setEditing] = useState<Collection | "new" | null>(null); const [deleting, setDeleting] = useState<Collection | null>(null); const [busy, setBusy] = useState(false);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { name: "", description: "" } });
  const query = useQuery({ queryKey: ["collections", workspace.id], queryFn: () => api.collections(workspace.id) });
  function edit(item: Collection | "new") { setEditing(item); form.reset(item === "new" ? { name: "", description: "" } : item); }
  async function save(data: z.infer<typeof schema>) { setBusy(true); try { if (editing === "new") await api.createCollection(workspace.id, data.name, data.description); else if (editing) await api.updateCollection(editing.id, data.name, data.description); await client.invalidateQueries({ queryKey: ["collections", workspace.id] }); setEditing(null); toast.success("Collection saved"); } catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); } }
  async function remove() { if (!deleting) return; setBusy(true); try { await api.deleteCollection(deleting.id); await client.invalidateQueries({ queryKey: ["collections", workspace.id] }); setDeleting(null); toast.success("Collection deleted; documents retained"); } catch (error) { toast.error(errorMessage(error)); } finally { setBusy(false); } }
  return <div className="stack"><div className="page-heading"><div><h1>Collections</h1><p>Bring related documents together around a project or idea.</p></div><Button onClick={() => edit("new")}><Plus size={16} />Create collection</Button></div>{query.isPending ? <Skeleton /> : query.error ? <ErrorState message={errorMessage(query.error)} retry={() => void query.refetch()} /> : query.data?.items.length ? <div className="collection-grid">{query.data.items.map(item => <article className="card card-body stack" key={item.id}><Folder className="accent" /><Link className="text-link" href={`/app/collections/${item.id}`}><h2>{item.name}</h2></Link><p className="muted">{item.description || "A collection of related knowledge."}</p><div className="row"><Button variant="secondary" onClick={() => edit(item)}>Edit</Button><Button variant="ghost" onClick={() => setDeleting(item)}>Delete</Button></div></article>)}</div> : <EmptyState icon={<Folder />} title="A place for related ideas" description="Create a collection, then upload or move documents into it." />}<Dialog open={!!editing} onOpenChange={open => { if (!open) setEditing(null); }} title={editing === "new" ? "Create collection" : "Edit collection"}><form className="form-stack" onSubmit={form.handleSubmit(save)}><div className="field"><label htmlFor="collection-name">Name</label><input id="collection-name" {...form.register("name")} />{form.formState.errors.name && <p role="alert" className="field-error">{form.formState.errors.name.message}</p>}</div><div className="field"><label htmlFor="collection-description">Description</label><textarea id="collection-description" {...form.register("description")} />{form.formState.errors.description && <p role="alert">{form.formState.errors.description.message}</p>}</div><Button type="submit" busy={busy}>Save collection</Button></form></Dialog><Dialog open={!!deleting} onOpenChange={open => { if (!open) setDeleting(null); }} title="Delete collection?" description="Documents remain in your workspace. Conversations scoped to this collection will require a new conversation with a valid scope."><p>{deleting?.name}</p><div className="dialog-actions"><Button variant="secondary" onClick={() => setDeleting(null)}>Cancel</Button><Button variant="danger" busy={busy} onClick={() => void remove()}>Delete collection</Button></div></Dialog></div>;
}
