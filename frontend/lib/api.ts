const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

export const api = {
  // Knowledge Bases
  listKBs: () => request<import("@/types").KnowledgeBase[]>("/api/kb"),
  createKB: (name: string, description = "") =>
    request<import("@/types").KnowledgeBase>("/api/kb", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  getKB: (id: string) => request<import("@/types").KnowledgeBase>(`/api/kb/${id}`),
  deleteKB: (id: string) => request<{ status: string }>(`/api/kb/${id}`, { method: "DELETE" }),

  // Documents
  listDocuments: (kbId: string) =>
    request<import("@/types").Document[]>(`/api/kb/${kbId}/documents`),
  uploadDocument: (kbId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return fetch(`${API_BASE}/api/kb/${kbId}/documents`, {
      method: "POST",
      body: formData,
    }).then((r) => {
      if (!r.ok) throw new Error("Upload failed");
      return r.json() as Promise<import("@/types").Document>;
    });
  },
  deleteDocument: (kbId: string, docId: string) =>
    request<{ status: string }>(`/api/kb/${kbId}/documents/${docId}`, { method: "DELETE" }),

  // Conversations
  listConversations: (kbId: string) =>
    request<import("@/types").Conversation[]>(`/api/kb/${kbId}/conversations`),
  getMessages: (convId: string) =>
    request<import("@/types").ConversationMessage[]>(`/api/conversations/${convId}/messages`),
};
