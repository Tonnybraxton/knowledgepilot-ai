"use client";
import { createContext, useContext } from "react";
import type { Session, Workspace } from "@/types/api";
export const WorkspaceContext = createContext<{ workspace: Workspace; workspaces: Workspace[]; session: Session; selectWorkspace: (id: string) => void } | null>(null);
export function useWorkspace() { const context = useContext(WorkspaceContext); if (!context) throw new Error("Workspace provider missing"); return context; }
