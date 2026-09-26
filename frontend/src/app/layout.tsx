import type { Metadata } from "next";
import { Providers } from "@/providers/providers";
import "./globals.css";
export const metadata: Metadata = { title: { default: "KnowledgePilot AI — Your knowledge, connected", template: "%s · KnowledgePilot" }, description: "A private workspace for your documents. Find the right passage, ask better questions, and trace every answer to its source." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en" suppressHydrationWarning><body><Providers>{children}</Providers></body></html>; }
