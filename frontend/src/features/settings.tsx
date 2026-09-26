"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { api } from "@/services/api";
import { useWorkspace } from "@/providers/workspace";
import { bytes, errorMessage } from "@/lib/utils";
import { Button, ErrorState } from "@/components/ui/primitives";

const schema = z.object({ name: z.string().trim().min(1, "Enter your name.").max(100), theme: z.enum(["light", "dark", "system"]) });
export function Settings() {
  const { workspace, session } = useWorkspace(); const client = useQueryClient(); const { theme, setTheme } = useTheme();
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { name: session.user.display_name, theme: theme === "dark" || theme === "light" ? theme : "system" } });
  const stats = useQuery({ queryKey: ["stats", workspace.id], queryFn: () => api.stats(workspace.id) });
  async function save(data: z.infer<typeof schema>) { try { await api.profile(data.name, data.theme); setTheme(data.theme); await client.invalidateQueries({ queryKey: ["session"] }); toast.success("Preferences saved"); } catch (error) { toast.error(errorMessage(error)); } }
  return <div className="stack"><div className="page-heading"><div><h1>Settings & usage</h1><p>Your profile, appearance, and workspace activity.</p></div></div><section className="card card-body stack"><h2>Profile & appearance</h2><p className="muted">{session.user.email}</p><form className="form-stack" onSubmit={form.handleSubmit(save)}><div className="field"><label htmlFor="display-name">Display name</label><input id="display-name" autoComplete="name" {...form.register("name")} />{form.formState.errors.name && <p role="alert" className="field-error">{form.formState.errors.name.message}</p>}</div><div className="field"><label htmlFor="theme">Theme</label><select id="theme" {...form.register("theme")}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></div><Button type="submit" busy={form.formState.isSubmitting}>Save preferences</Button></form></section><section className="card card-body stack"><h2>Workspace usage</h2>{stats.error ? <ErrorState message={errorMessage(stats.error)} /> : <dl className="usage-grid"><div><dt>Documents</dt><dd>{stats.data?.documents ?? "—"}</dd></div><div><dt>Original file storage</dt><dd>{stats.data ? bytes(stats.data.storage_bytes) : "—"}</dd></div><div><dt>Recorded AI operations</dt><dd>{stats.data?.ai_requests ?? "—"}</dd></div><div><dt>Recorded tokens</dt><dd>{stats.data?.tokens.toLocaleString() ?? "—"}</dd></div></dl>}<p className="small muted">Usage includes embeddings and completed generation calls. Interrupted provider requests may not report tokens. Provider billing remains authoritative.</p></section></div>;
}
