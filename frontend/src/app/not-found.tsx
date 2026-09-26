import Link from "next/link";
export default function NotFound() { return <main className="main-content stack"><h1>Page not found</h1><p>This page is unavailable or has moved.</p><Link href="/app/dashboard" className="text-link">Go to your workspace</Link></main>; }
