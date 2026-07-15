"use client";
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Files, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { ChatInterface } from "@/components/ChatInterface";
import { Sidebar } from "@/components/Sidebar";
import { DocumentPanel } from "@/components/DocumentPanel";
import type { KnowledgeBase, Document as Doc } from "@/types";

export default function KBPage() {
  const params = useParams();
  const router = useRouter();
  const kbId = params.kbId as string;

  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [docPanelOpen, setDocPanelOpen] = useState(false);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [convRefreshTrigger, setConvRefreshTrigger] = useState(0);
  const [chatKey, setChatKey] = useState(0);

  const loadData = useCallback(async () => {
    try {
      const [kbData, docsData] = await Promise.all([
        api.getKB(kbId),
        api.listDocuments(kbId),
      ]);
      setKb(kbData);
      setDocuments(docsData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleUploadComplete = () => {
    loadData();
  };

  const handleDeleteDocument = async (docId: string) => {
    await api.deleteDocument(kbId, docId);
    loadData();
  };

  const handleSelectConversation = (id: string) => {
    setActiveConvId(id);
    setChatKey((prev) => prev + 1);
    if (window.innerWidth < 1024) setSidebarOpen(false);
  };

  const handleNewChat = () => {
    setActiveConvId(null);
    setChatKey((prev) => prev + 1);
    if (window.innerWidth < 1024) setSidebarOpen(false);
  };

  const handleConversationCreated = (convId: string) => {
    setActiveConvId(convId);
    setConvRefreshTrigger((prev) => prev + 1);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#f4f4f5]">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!kb) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#f4f4f5]">
        <p className="text-gray-500">Knowledge base not found.</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#f4f4f5]">
      <Sidebar
        kbId={kbId}
        activeConvId={activeConvId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((prev) => !prev)}
        refreshTrigger={convRefreshTrigger}
        kbName={kb.name}
      />

      <div className="flex flex-col flex-1 min-w-0">
        <header className="flex items-center justify-between px-4 py-2.5 bg-white border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.push("/")}
              className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
              title="Back to home"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <h1 className="text-sm font-semibold text-gray-800">{kb.name}</h1>
            <span className="text-[11px] text-gray-400 ml-1">{documents.length} docs</span>
          </div>

          <button
            onClick={() => setDocPanelOpen((prev) => !prev)}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors
              ${docPanelOpen
                ? "bg-indigo-100 text-indigo-700"
                : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"}
            `}
          >
            <Files className="w-3.5 h-3.5" />
            Documents
          </button>
        </header>

        <main className="flex-1 flex flex-col min-h-0">
          <ChatInterface
            key={chatKey}
            kbId={kbId}
            initialConvId={activeConvId}
            onConversationCreated={handleConversationCreated}
            onUploadComplete={handleUploadComplete}
          />
        </main>
      </div>

      <DocumentPanel
        kbId={kbId}
        documents={documents}
        isOpen={docPanelOpen}
        onClose={() => setDocPanelOpen(false)}
        onUploadComplete={handleUploadComplete}
        onDeleteDocument={handleDeleteDocument}
      />
    </div>
  );
}
