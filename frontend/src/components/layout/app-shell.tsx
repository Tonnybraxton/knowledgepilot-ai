"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { ChevronDown, ChevronsLeft, FileText, Folder, LayoutDashboard, LogOut, Menu, MessageSquare, Moon, Plus, Search, Settings, ShieldCheck, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Brand } from "./brand";
import { Button, Dialog, ErrorState, Skeleton, Tooltip } from "@/components/ui/primitives";
import { api, ApiError, setCsrf } from "@/services/api";
import { WorkspaceContext } from "@/providers/workspace";
import { cn, errorMessage } from "@/lib/utils";
import { useStoredValue } from "@/hooks/use-stored-value";

const navigation = [
  { href: "/app/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/app/search", label: "Search knowledge", icon: Search },
  { href: "/app/documents", label: "Documents", icon: FileText },
  { href: "/app/collections", label: "Collections", icon: Folder },
  { href: "/app/conversations", label: "Conversations", icon: MessageSquare },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter(); const path = usePathname(); const client = useQueryClient(); const { resolvedTheme, setTheme } = useTheme();
  const [workspaceId, setWorkspaceId] = useStoredValue("kp-workspace", ""); const [mobile, setMobile] = useState(false); const [sidebarState, setSidebarState] = useStoredValue("kp-sidebar", "expanded");
  const collapsed = sidebarState === "collapsed";
  const setCollapsed = (value: boolean) => setSidebarState(value ? "collapsed" : "expanded");
  const [palette, setPalette] = useState(false); const [command, setCommand] = useState(""); const [createOpen, setCreateOpen] = useState(false); const [name, setName] = useState(""); const [creating, setCreating] = useState(false);
  const session = useQuery({ queryKey: ["session"], queryFn: async () => { const data = await api.session(); setCsrf(data.csrf_token); return data; }, retry: false });
  const workspaces = useQuery({ queryKey: ["workspaces"], queryFn: api.workspaces, enabled: !!session.data });
  const workspace = workspaces.data?.find(item => item.id === workspaceId) ?? workspaces.data?.[0];
  useEffect(() => {
    const expire = () => { client.clear(); setCsrf(""); router.replace("/login?expired=1"); };
    window.addEventListener("session-expired", expire);
    const keyboard = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key === "k") { event.preventDefault(); setPalette(value => !value); } };
    window.addEventListener("keydown", keyboard);
    return () => { window.removeEventListener("session-expired", expire); window.removeEventListener("keydown", keyboard); };
  }, [client, router]);
  useEffect(() => { if (session.error instanceof ApiError && session.error.status === 401) router.replace("/login?expired=1"); }, [session.error, router]);
  function selectWorkspace(id: string) { setWorkspaceId(id); localStorage.setItem("kp-workspace", id); setMobile(false); router.push("/app/dashboard"); }
  async function createWorkspace(event: React.FormEvent) { event.preventDefault(); setCreating(true); try { const item = await api.createWorkspace(name); await client.invalidateQueries({ queryKey: ["workspaces"] }); selectWorkspace(item.id); setCreateOpen(false); setName(""); toast.success("Workspace created"); } catch (error) { toast.error(errorMessage(error)); } finally { setCreating(false); } }
  async function logout() { try { await api.logout(); setCsrf(""); client.clear(); router.push("/login"); } catch (error) { toast.error(errorMessage(error)); } }
  const label = path.includes("/chat") ? "AI chat" : navigation.find(item => path.startsWith(item.href))?.label ?? "Settings";
  if (session.isPending || (session.data && workspaces.isPending)) return <main className="main-content"><Skeleton rows={5} /></main>;
  if (session.error || workspaces.error) return <main className="main-content"><ErrorState message={errorMessage(session.error ?? workspaces.error)} retry={() => { void session.refetch(); void workspaces.refetch(); }} /></main>;
  if (!session.data || !workspace || !workspaces.data) return <main className="main-content"><ErrorState message="No workspace is available. Sign in again to reload your account." /><Link href="/login">Sign in</Link></main>;
  const user = session.data.user;
  const sidebar = <aside className="sidebar"><Brand href="/app/dashboard" /><Dropdown.Root><Dropdown.Trigger className="workspace-switch"><div className="workspace-avatar">{workspace.name[0].toUpperCase()}</div><span>{workspace.name}</span><ChevronDown size={14} /></Dropdown.Trigger><Dropdown.Portal><Dropdown.Content className="dropdown" sideOffset={5}>{workspaces.data.map(item => <Dropdown.Item className="dropdown-item" key={item.id} onSelect={() => selectWorkspace(item.id)}>{item.name}</Dropdown.Item>)}<Dropdown.Separator /><Dropdown.Item className="dropdown-item" onSelect={() => setCreateOpen(true)}><Plus size={15} />Create workspace</Dropdown.Item></Dropdown.Content></Dropdown.Portal></Dropdown.Root><Link href="/app/chat" className="button button-primary sidebar-new" onClick={() => setMobile(false)}><Plus size={17} /><span className="sidebar-new-label">New conversation</span></Link><div><div className="sidebar-label">Workspace</div><nav aria-label="Main navigation">{navigation.map(item => <Link key={item.href} href={item.href} className={cn("nav-link", path.startsWith(item.href) && "active")} onClick={() => setMobile(false)} aria-current={path.startsWith(item.href) ? "page" : undefined} title={collapsed ? item.label : undefined}><item.icon size={18} strokeWidth={1.7} /><span className="nav-label">{item.label}</span></Link>)}</nav></div><div className="sidebar-bottom"><div className="privacy-note"><ShieldCheck size={16} /><span>Your knowledge stays private.<br />Answers stay connected to sources.</span></div><Link className={cn("nav-link", path.includes("settings") && "active")} href="/app/settings" onClick={() => setMobile(false)}><Settings size={18} /><span className="nav-label">Settings & usage</span></Link><div className="profile-row"><div className="avatar">{user.display_name.slice(0, 2).toUpperCase()}</div><div className="profile-info"><strong>{user.display_name}</strong><span>{user.email}</span></div><Tooltip label="Sign out"><button className="icon-button" onClick={() => void logout()} aria-label="Sign out"><LogOut size={16} /></button></Tooltip></div></div></aside>;
  return <WorkspaceContext.Provider value={{ workspace, workspaces: workspaces.data, session: session.data, selectWorkspace }}><a className="skip-link" href="#main-content">Skip to content</a><div className={cn("app-shell", collapsed && "collapsed")}><div className="desktop-sidebar">{sidebar}</div><div className="workspace-main"><header className="topbar"><div className="row"><button className="icon-button mobile-only" onClick={() => setMobile(true)} aria-label="Open navigation"><Menu size={20} /></button><Tooltip label={collapsed ? "Expand sidebar" : "Collapse sidebar"}><button className="icon-button desktop-sidebar" onClick={() => { setCollapsed(!collapsed); localStorage.setItem("kp-sidebar", collapsed ? "expanded" : "collapsed"); }} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}><ChevronsLeft size={17} /></button></Tooltip><div className="breadcrumb"><span>Workspace</span><span>/</span><strong>{label}</strong></div></div><div className="row"><button className="global-search" onClick={() => setPalette(true)} aria-label="Open command palette"><Search size={15} /><span>Search or jump to…</span><kbd>⌘ K</kbd></button><Tooltip label="Toggle theme"><button className="icon-button" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")} aria-label="Toggle theme">{resolvedTheme === "dark" ? <Sun size={18} /> : <Moon size={18} />}</button></Tooltip></div></header><main className="main-content" id="main-content" key={workspace.id}>{children}</main></div></div><Dialog open={mobile} onOpenChange={setMobile} title="Navigation" className="mobile-navigation">{sidebar}</Dialog><Dialog open={palette} onOpenChange={setPalette} title="Jump to your knowledge"><input autoFocus aria-label="Search commands" placeholder="Type a page or action…" value={command} onChange={event => setCommand(event.target.value)} /><div className="command-list">{[{ href: "/app/chat", label: "New conversation", icon: Plus }, ...navigation, { href: "/app/settings", label: "Settings & preferences", icon: Settings }].filter(item => item.label.toLowerCase().includes(command.toLowerCase())).map(item => <Link key={item.href} href={item.href} onClick={() => setPalette(false)}><item.icon size={17} />{item.label}</Link>)}</div></Dialog><Dialog open={createOpen} onOpenChange={setCreateOpen} title="Create a workspace" description="Give a separate project or area of knowledge its own space."><form onSubmit={createWorkspace} className="form-stack"><div className="field"><label htmlFor="workspace-name">Workspace name</label><input id="workspace-name" required minLength={1} maxLength={100} value={name} onChange={event => setName(event.target.value)} /></div><Button busy={creating} type="submit">Create workspace</Button></form></Dialog></WorkspaceContext.Provider>;
}
