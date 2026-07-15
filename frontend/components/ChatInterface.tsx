"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Volume2, Square, Loader2, Bot, User, Globe, FileText, ImageIcon } from "lucide-react";
import clsx from "clsx";
import { WelcomeScreen } from "./WelcomeScreen";
import { ChatInput } from "./ChatInput";
import { fileToBase64 } from "@/lib/api";
import type { Message, Citation, ConversationMessage } from "@/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChatInterfaceProps {
  kbId: string;
  initialConvId?: string | null;
  onConversationCreated?: (convId: string) => void;
  onUploadComplete?: () => void;
}

export function ChatInterface({ kbId, initialConvId, onConversationCreated, onUploadComplete }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(!!initialConvId);
  const [convId, setConvId] = useState<string | null>(initialConvId || null);
  const [generatingTts, setGeneratingTts] = useState(false);
  const [processingImages, setProcessingImages] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => scrollToBottom(), [messages]);

  const handleStop = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
  };

  useEffect(() => {
    if (!initialConvId) {
      setMessages([]);
      setConvId(null);
      setInitialLoading(false);
      return;
    }

    let cancelled = false;
    setInitialLoading(true);
    fetch(`${API}/api/conversations/${initialConvId}/messages`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load messages");
        return r.json() as Promise<ConversationMessage[]>;
      })
      .then((convMessages) => {
        if (cancelled) return;
        const mapped: Message[] = convMessages.map((m) => ({
          role: m.role,
          content: m.content,
          citations: [],
        }));
        setMessages(mapped);
        setConvId(initialConvId);
      })
      .catch(console.error)
      .finally(() => {
        if (!cancelled) setInitialLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [initialConvId]);

  const generateSpeech = useCallback(
    async (text: string, msgIndex: number) => {
      if (!text.trim()) return;
      setGeneratingTts(true);
      try {
        const res = await fetch(`${API}/api/tts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        if (!res.ok) return;
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[msgIndex]) {
            updated[msgIndex] = { ...updated[msgIndex], audioUrl: url };
          }
          return updated;
        });
      } catch {
      } finally {
        setGeneratingTts(false);
      }
    },
    []
  );

  const handleSend = async (query: string, files?: File[]) => {
    if (loading) return;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const imageFiles = files?.filter((f) => f.type.startsWith("image/")) ?? [];
    const nonImageFiles = files?.filter((f) => !f.type.startsWith("image/")) ?? [];
    const imagePreviews = imageFiles.map((f) => URL.createObjectURL(f));

    setLoading(true);

    let displayContent = query.trim();
    if (!displayContent) {
      if (nonImageFiles.length > 0) {
        displayContent = `Uploaded document: ${nonImageFiles.map((f) => f.name).join(", ")}`;
      } else if (imageFiles.length > 0) {
        displayContent = "(Sent an image)";
      }
    }

    const userMsg: Message = {
      role: "user",
      content: displayContent || "(Empty message)",
      images: imagePreviews.length > 0 ? imagePreviews : undefined,
    };
    setMessages((prev) => [...prev, userMsg]);

    const assistantIdx = messages.length + 1;
    const assistantMsg: Message = { role: "assistant", content: "", citations: [] };
    setMessages((prev) => [...prev, assistantMsg]);

    // Upload non-image files first to ingest them into the active Knowledge Base via RAG
    if (nonImageFiles.length > 0) {
      for (const file of nonImageFiles) {
        try {
          const formData = new FormData();
          formData.append("file", file);
          const uploadRes = await fetch(`${API}/api/kb/${kbId}/documents`, {
            method: "POST",
            body: formData,
            signal: controller.signal,
          });
          if (!uploadRes.ok) {
            const errText = await uploadRes.text().catch(() => "Upload failed");
            throw new Error(`Failed to upload ${file.name}: ${errText}`);
          }
        } catch (err) {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: `Error: ${err instanceof Error ? err.message : "Failed to process files"}`,
            };
            return updated;
          });
          setLoading(false);
          return;
        }
      }
      // Refresh documents list in the UI side-panel
      onUploadComplete?.();
    }

    let base64Images: string[] = [];
    if (imageFiles.length > 0) {
      setProcessingImages(true);
      base64Images = await Promise.all(imageFiles.map(fileToBase64));
      setProcessingImages(false);
    }

    let finalQuery = query.trim();
    if (!finalQuery) {
      if (nonImageFiles.length > 0) {
        finalQuery = `Summarize the attached document: ${nonImageFiles.map((f) => f.name).join(", ")}`;
      } else if (imageFiles.length > 0) {
        finalQuery = "Describe the attached image(s)";
      }
    }

    try {
      const response = await fetch(`${API}/api/kb/${kbId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: finalQuery || "Hello",
          conversation_id: convId,
          images: base64Images,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errText = await response.text().catch(() => "Request failed");
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: `Error: ${errText}`,
          };
          return updated;
        });
        setLoading(false);
        return;
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let fullContent = "";
      let newConvId: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "token") {
              fullContent += data.content;
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = { ...updated[updated.length - 1], content: fullContent };
                return updated;
              });
            } else if (data.type === "done") {
              newConvId = data.conversation_id;
              setConvId(newConvId);
              if (newConvId) onConversationCreated?.(newConvId);
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  citations: data.citations || [],
                };
                return updated;
              });
              generateSpeech(fullContent, assistantIdx);
            } else if (data.type === "error") {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: `Error: ${data.content}`,
                };
                return updated;
              });
            }
          } catch {
            /* partial line */
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User stopped generation — keep partial content, no error message
      } else {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: `Network error: ${err instanceof Error ? err.message : "Unknown error"}`,
          };
          return updated;
        });
      }
    } finally {
      abortControllerRef.current = null;
      setLoading(false);
    }
  };

  const handleSuggestionClick = (text: string) => {
    handleSend(text);
  };

  if (initialLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
        <p className="text-xs text-gray-400">Loading conversation...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <WelcomeScreen onSuggestionClick={handleSuggestionClick} />
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-1">
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                message={msg}
                isLast={i === messages.length - 1}
                isStreaming={loading && i === messages.length - 1 && msg.role === "assistant"}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <ChatInput onSend={handleSend} onStop={handleStop} disabled={loading} />
    </div>
  );
}

function ChatMessage({
  message,
  isLast,
  isStreaming,
}: {
  message: Message;
  isLast: boolean;
  isStreaming: boolean;
}) {
  const isUser = message.role === "user";
  const [playing, setPlaying] = useState(false);
  const [localAudioUrl, setLocalAudioUrl] = useState<string | null>(message.audioUrl || null);
  const [loadingAudio, setLoadingAudio] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const handlePlayToggle = async () => {
    if (playing) {
      audioRef.current?.pause();
      setPlaying(false);
      return;
    }

    const urlToPlay = localAudioUrl || message.audioUrl;
    if (urlToPlay) {
      const audio = new Audio(urlToPlay);
      audioRef.current = audio;
      audio.onended = () => setPlaying(false);
      audio.play().then(() => setPlaying(true)).catch((e) => console.error("Audio playback failed", e));
      return;
    }

    // Generate speech audio on demand if not present
    if (!message.content.trim() || loadingAudio) return;

    setLoadingAudio(true);
    try {
      const res = await fetch(`${API}/api/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: message.content }),
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        setLocalAudioUrl(url);

        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => setPlaying(false);
        audio.play().then(() => setPlaying(true)).catch((e) => console.error("Audio playback failed", e));
      } else {
        console.error("Failed to generate TTS");
      }
    } catch (err) {
      console.error("Failed to generate TTS", err);
    } finally {
      setLoadingAudio(false);
    }
  };

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
    };
  }, []);

  return (
    <div className={clsx("flex gap-4 px-4 py-4 message-enter", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center shadow-sm">
          <Bot className="w-4.5 h-4.5 text-white" />
        </div>
      )}

      <div className={clsx("max-w-[78%]", isUser && "flex flex-col items-end")}>
        {!isUser && (
          <p className="text-[11px] font-semibold text-gray-400 mb-1.5 ml-0.5">Inquix</p>
        )}

        <div
          className={clsx(
            "text-sm leading-relaxed",
            isUser
              ? "bg-[#e3ecfc] text-gray-800 rounded-2xl px-4 py-2.5 shadow-[0_1px_2px_rgba(0,0,0,0.01)] border border-indigo-100/50"
              : "text-gray-800 py-0.5 font-normal"
          )}
        >
          {message.images && message.images.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {message.images.map((src, i) => (
                <div
                  key={i}
                  className="relative w-20 h-20 rounded-lg overflow-hidden border border-white/20 shrink-0"
                >
                  <img
                    src={src}
                    alt={`Uploaded ${i + 1}`}
                    className="w-full h-full object-cover"
                  />
                </div>
              ))}
            </div>
          )}

          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className={clsx("markdown-body", isStreaming && !message.content && "min-h-[20px]")}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content || (isStreaming ? "..." : "")}
              </ReactMarkdown>
              {isStreaming && message.content && <span className="typing-cursor" />}
            </div>
          )}
        </div>

        {!isUser && message.content && !isStreaming && (
          <div className="flex items-center gap-3 mt-1.5 ml-1">
            <button
              onClick={handlePlayToggle}
              disabled={loadingAudio}
              className="flex items-center gap-1.5 text-[11px] text-gray-400 hover:text-indigo-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              title={playing ? "Stop" : "Listen"}
            >
              {loadingAudio ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-500" />
              ) : playing ? (
                <Square className="w-3.5 h-3.5" />
              ) : (
                <Volume2 className="w-3.5 h-3.5" />
              )}
              {loadingAudio ? "Generating audio..." : playing ? "Stop" : "Listen"}
            </button>
          </div>
        )}

        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-3.5">
            <div className="flex flex-wrap gap-1.5">
              {message.citations.slice(0, 6).map((cite, i) => (
                <div
                  key={cite.id}
                  className="flex items-center gap-1.5 px-2.5 py-1 bg-white border border-gray-200/80 rounded-full text-[10px] text-gray-500 shadow-[0_1px_2px_rgba(0,0,0,0.01)] hover:border-indigo-300 transition-colors"
                >
                  {cite.source_type === "web" ? (
                    <Globe className="w-3 h-3 shrink-0" />
                  ) : (
                    <FileText className="w-3 h-3 shrink-0" />
                  )}
                  {cite.metadata?.url ? (
                    <a
                      href={cite.metadata.url as string}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate max-w-[100px] hover:text-indigo-600 hover:underline"
                    >
                      {cite.filename}
                    </a>
                  ) : (
                    <span className="truncate max-w-[100px]">{cite.filename}</span>
                  )}
                  {cite.similarity && cite.source_type !== "web" && (
                    <span className="text-gray-300">{Math.round(cite.similarity * 100)}%</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
          <User className="w-4 h-4 text-gray-500" />
        </div>
      )}
    </div>
  );
}
