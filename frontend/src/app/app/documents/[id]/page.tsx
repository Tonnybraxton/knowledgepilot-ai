import { DocumentDetail } from "@/features/document-detail";
export default async function Page({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ chunk?: string }> }) { const { id } = await params; const { chunk } = await searchParams; return <DocumentDetail id={id} chunk={chunk} />; }
