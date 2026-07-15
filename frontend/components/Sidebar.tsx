"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { Plus, MessageSquare, Trash2, PanelLeftClose, PanelLeft, Loader2 } from "lucide-react";
import clsx from "clsx";
import type { Conversation } from "@/types";

interface SidebarProps {
  kbId: string;
  activeConvId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
  onToggle: () => void;
  refreshTrigger: number;
  kbName: string;
}

export function Sidebar({
  kbId,
  activeConvId,
  onSelectConversation,
  onNewChat,
  isOpen,
  onToggle,
  refreshTrigger,
  kbName,
}: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listConversations(kbId)
      .then((list) => {
        if (!cancelled) setConversations(list);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [kbId, refreshTrigger]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/conversations/${id}`,
        { method: "DELETE" }
      );
      setConversations((prev) => prev.filter((c) => c.id !== id));
    } catch {}
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 86400000) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (diff < 604800000) return d.toLocaleDateString([], { weekday: "short" });
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 bg-black/30 z-20 lg:hidden" onClick={onToggle} />
      )}

      <aside
        className={clsx(
          "fixed lg:static inset-y-0 left-0 z-30 flex flex-col bg-[#18181b] text-white transition-all duration-300 ease-in-out border-r border-zinc-800/40",
          isOpen ? "w-[260px]" : "w-0 lg:w-0 overflow-hidden"
        )}
      >
        <div className={clsx("flex flex-col h-full w-[260px]", !isOpen && "hidden lg:hidden")}>
          <div className="flex items-center justify-between p-3 shrink-0">
            <button
              onClick={onNewChat}
              className="flex items-center gap-2 px-3 py-2 text-sm text-zinc-300 hover:text-white hover:bg-zinc-800/80 rounded-lg transition-colors w-full border border-zinc-800"
            >
              <Plus className="w-4 h-4" />
              <span>New chat</span>
            </button>
            <button
              onClick={onToggle}
              className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800/80 transition-colors ml-1"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto sidebar-scroll px-2 pb-2 space-y-0.5">
            {loading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
              </div>
            ) : conversations.length === 0 ? (
              <p className="text-xs text-gray-500 text-center py-6">No conversations yet</p>
            ) : (
              conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => onSelectConversation(conv.id)}
                  className={clsx(
                    "flex items-center gap-2.5 w-full px-3 py-2.5 text-sm rounded-lg text-left transition-colors group",
                    conv.id === activeConvId
                      ? "bg-zinc-850 bg-zinc-800 text-white"
                      : "text-zinc-400 hover:bg-zinc-800/40 hover:text-zinc-200"
                  )}
                >
                  <MessageSquare className="w-4 h-4 shrink-0 text-zinc-500 group-hover:text-indigo-400 transition-colors" />
                  <span className="truncate flex-1">{conv.title || "Chat"}</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">{formatDate(conv.created_at)}</span>
                  <button
                    onClick={(e) => handleDelete(e, conv.id)}
                    className="p-0.5 text-zinc-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </button>
              ))
            )}
          </div>

          <div className="p-3 border-t border-zinc-800/60 shrink-0">
            <div className="flex items-center gap-2.5 text-xs text-zinc-400">
              <div className="w-6 h-6 rounded-lg bg-indigo-600 flex items-center justify-center text-white text-[10px] font-bold shrink-0 shadow-md">
                I
              </div>
              <span className="truncate font-semibold">{kbName}</span>
            </div>
          </div>
        </div>
      </aside>

      {!isOpen && (
        <button
          onClick={onToggle}
          className="fixed top-3 left-3 z-20 p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded-lg transition-colors lg:static lg:z-auto"
        >
          <PanelLeft className="w-5 h-5" />
        </button>
      )}
    </>
  );
}
