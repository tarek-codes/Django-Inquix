"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Brain, Plus, Trash2, Loader2, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import type { KnowledgeBase } from "@/types";

export default function HomePage() {
  const router = useRouter();
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    api.listKBs().then(setKbs).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const kb = await api.createKB(newName.trim());
      router.push(`/kb/${kb.id}`);
    } catch (e) {
      console.error(e);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    await api.deleteKB(id);
    setKbs((prev) => prev.filter((k) => k.id !== id));
  };

  return (
    <div className="min-h-screen bg-[#f4f4f5] flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-lg">
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 mb-5 shadow-lg shadow-indigo-200">
            <Brain className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Inquix</h1>
          <p className="text-sm text-gray-500 mt-1.5">Multi-modal RAG — upload documents and ask questions</p>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
          </div>
        ) : kbs.length === 0 ? (
          <div className="space-y-4">
            <div className="text-center py-10 bg-white rounded-2xl border border-gray-200 shadow-sm">
              <MessageSquare className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No knowledge bases yet</p>
              <p className="text-xs text-gray-400 mt-1">Create one to start chatting with your documents</p>
            </div>

            {showCreate ? (
              <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4 space-y-3">
                <input
                  type="text"
                  placeholder="Name your knowledge base..."
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => { setShowCreate(false); setNewName(""); }}
                    className="flex-1 px-4 py-2 text-sm border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors text-gray-600"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreate}
                    disabled={creating || !newName.trim()}
                    className="flex-1 px-4 py-2 text-sm bg-gray-900 text-white rounded-xl hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {creating ? "Creating..." : "Create"}
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowCreate(true)}
                className="w-full flex items-center justify-center gap-2 px-4 py-3.5 border-2 border-dashed border-gray-300 rounded-2xl text-sm text-gray-500 hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50/30 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Create Knowledge Base
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {kbs.map((kb) => (
              <div
                key={kb.id}
                onClick={() => router.push(`/kb/${kb.id}`)}
                className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-2xl cursor-pointer hover:border-indigo-200 hover:shadow-sm transition-all"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
                    <Brain className="w-5 h-5 text-indigo-600" />
                  </div>
                  <div>
                    <h3 className="font-medium text-gray-900 text-sm">{kb.name}</h3>
                    <p className="text-xs text-gray-400">{kb.document_count} documents</p>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(kb.id);
                  }}
                  className="p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}

            <button
              onClick={() => setShowCreate(true)}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-gray-300 rounded-2xl text-sm text-gray-500 hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50/30 transition-colors mt-3"
            >
              <Plus className="w-4 h-4" />
              New Knowledge Base
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
