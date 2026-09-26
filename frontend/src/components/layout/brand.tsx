import { Orbit } from "lucide-react";
import Link from "next/link";
export function Brand({ href = "/" }: { href?: string }) { return <Link href={href} className="brand" aria-label="KnowledgePilot home"><span className="brand-symbol"><Orbit size={22} strokeWidth={1.7} /></span><span>KnowledgePilot</span><small>AI</small></Link>; }
