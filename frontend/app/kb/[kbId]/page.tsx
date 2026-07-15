"use client";
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Files, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { ChatInterface } from "@/components/ChatInterface";
import { Sidebar } from "@/components/Sidebar";
import { DocumentPanel } from "@/components/DocumentPanel";
import { FileUpload } from "@/components/FileUpload";
import { DocumentList } from "@/components/DocumentList";
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
    setActiveConvId(null);
    setChatKey((prev) => prev + 1);
    loadData();
  }, [kbId, loadData]);

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
    <div className="flex h-screen bg-[#f8f9fc] overflow-hidden">
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

      <div className="flex flex-col flex-1 min-w-0 h-full">
        <header className="flex items-center justify-between px-6 py-3.5 bg-white border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/")}
              className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
              title="Back to home"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <h1 className="text-base font-semibold text-gray-800 tracking-tight">{kb.name}</h1>
          </div>

          <div className="flex items-center gap-2">
            {/* Toggle chat history on mobile */}
            <button
              onClick={() => setSidebarOpen((prev) => !prev)}
              className={`lg:hidden px-3 py-1.5 text-xs font-semibold rounded-lg border border-gray-200 ${
                sidebarOpen ? "bg-gray-100 text-gray-800" : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              Chats
            </button>

            {/* Toggle Sources for mobile */}
            <button
              onClick={() => setDocPanelOpen((prev) => !prev)}
              className={`md:hidden flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors border border-gray-200 ${
                docPanelOpen
                  ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                  : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              <Files className="w-3.5 h-3.5" />
              Sources
            </button>
          </div>
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* Inline Sources list on desktop (hidden on mobile/tablet) */}
          <div className="hidden md:flex flex-col w-[320px] bg-white border-r border-gray-200 h-full shrink-0">
            <div className="p-4 border-b border-gray-100 shrink-0">
              <h2 className="text-sm font-semibold text-gray-800 mb-3">Sources</h2>
              <FileUpload kbId={kbId} onUploadComplete={handleUploadComplete} />
            </div>
            <div className="flex-1 overflow-y-auto p-4 sidebar-scroll">
              <DocumentList documents={documents} onDelete={handleDeleteDocument} />
            </div>
          </div>

          {/* Chat Workspace */}
          <div className="flex-1 flex flex-col h-full bg-[#f8f9fc] min-w-0">
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
        </div>
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
