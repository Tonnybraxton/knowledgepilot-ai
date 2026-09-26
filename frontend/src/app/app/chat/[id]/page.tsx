import { Chat } from "@/features/chat";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <Chat conversationId={id} key={id} />; }
