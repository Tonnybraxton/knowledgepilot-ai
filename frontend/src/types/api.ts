export interface User { id: string; email: string; display_name: string; preferences: { theme?: string } }
export interface Session { user: User; csrf_token: string }
export interface Workspace { id: string; name: string; owner_id: string }
export interface Collection { id: string; workspace_id: string; name: string; description: string }
export type DocumentStatus = "queued" | "extracting" | "chunking" | "embedding" | "indexing" | "ready" | "failed";
export interface Document { id: string; workspace_id: string; collection_id: string | null; filename: string; mime_type: string; size_bytes: number; status: DocumentStatus; chunk_count: number; page_count: number | null; processing_error: string | null; created_at: string }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface Scope { document_ids?: string[]; collection_id?: string | null }
export interface Conversation { id: string; title: string; retrieval_scope: Scope; updated_at: string }
export interface Citation { citation_number: number; document_id: string | null; chunk_id: string | null; document_name: string; excerpt: string; page_number: number | null; section_title: string | null }
export interface Message { id: string; role: "user" | "assistant"; content: string; status: string; created_at: string; citations: Citation[] }
export interface SearchHit { chunk_id: string; document_id: string; document_name: string; content: string; page_number: number | null; section_title: string | null; score: number }
export interface Chunk { id: string; content: string; page_number: number | null; section_title: string | null; chunk_index: number }
export interface Stats { documents: number; ready: number; processing: number; conversations: number; storage_bytes: number; ai_requests: number; tokens: number }
