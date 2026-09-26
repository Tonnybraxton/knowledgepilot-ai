"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { AlertCircle, ArrowLeft, ArrowRight, Loader2, X } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Button({ className, variant = "primary", busy, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; busy?: boolean }) {
  return <button className={cn("button", `button-${variant}`, className)} {...props} disabled={props.disabled || busy}>{busy && <Loader2 size={16} className="spin" aria-hidden="true" />}{children}</button>;
}
export function Dialog({ open, onOpenChange, title, description, children, className }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description?: string; children: ReactNode; className?: string }) {
  return <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}><DialogPrimitive.Portal><DialogPrimitive.Overlay className="dialog-overlay" /><DialogPrimitive.Content className={cn("dialog-content", className)} aria-describedby={description ? undefined : undefined}><div className="dialog-heading"><DialogPrimitive.Title>{title}</DialogPrimitive.Title><DialogPrimitive.Close className="icon-button" aria-label="Close dialog"><X size={20} /></DialogPrimitive.Close></div>{description && <DialogPrimitive.Description className="muted">{description}</DialogPrimitive.Description>}{children}</DialogPrimitive.Content></DialogPrimitive.Portal></DialogPrimitive.Root>;
}
export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return <TooltipPrimitive.Provider delayDuration={350}><TooltipPrimitive.Root><TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger><TooltipPrimitive.Portal><TooltipPrimitive.Content className="tooltip" sideOffset={6}>{label}</TooltipPrimitive.Content></TooltipPrimitive.Portal></TooltipPrimitive.Root></TooltipPrimitive.Provider>;
}
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="error-state" role="alert"><AlertCircle size={18} /><span>{message}</span>{retry && <Button variant="secondary" onClick={retry}>Retry</Button>}</div>;
}
export function Skeleton({ rows = 3 }: { rows?: number }) { return <div className="skeleton-stack" aria-label="Loading" role="status">{Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" />)}</div>; }
export function EmptyState({ icon, title, description, children }: { icon: ReactNode; title: string; description: string; children?: ReactNode }) { return <div className="empty-state"><div className="empty-icon">{icon}</div><h2>{title}</h2><p>{description}</p>{children}</div>; }
export function Pagination({ page, total, pageSize, onChange }: { page: number; total: number; pageSize: number; onChange: (page: number) => void }) {
  if (total <= pageSize) return null;
  return <nav className="pagination" aria-label="Pagination"><span>{total} results · Page {page} of {Math.ceil(total / pageSize)}</span><Button variant="secondary" disabled={page === 1} onClick={() => onChange(page - 1)} aria-label="Previous page"><ArrowLeft size={16} /></Button><Button variant="secondary" disabled={page * pageSize >= total} onClick={() => onChange(page + 1)} aria-label="Next page"><ArrowRight size={16} /></Button></nav>;
}
