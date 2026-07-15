"use client";
import { useState, useRef, useEffect } from "react";
import { Send, Mic, MicOff, Loader2, Plus, FileAudio, FileText, X, Square } from "lucide-react";
import clsx from "clsx";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PendingFile {
  id: string;
  file: File;
  preview: string | null;
  status: "pending" | "uploading" | "transcribing" | "done" | "error";
  error?: string;
}

interface ChatInputProps {
  onSend: (text: string, files?: File[]) => void;
  onStop?: () => void;
  disabled: boolean;
  onInputChange?: (text: string) => void;
}

let fileIdCounter = 0;
function nextFileId() {
  return `file_${++fileIdCounter}_${Date.now()}`;
}

export function ChatInput({ onSend, onStop, disabled, onInputChange }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [recording, setRecording] = useState(false);
  const [transcribingAudio, setTranscribingAudio] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const [dragOver, setDragOver] = useState(false);

  const hasContent = input.trim().length > 0 || pendingFiles.length > 0;

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + "px";
    }
  }, [input]);

  useEffect(() => {
    if (!disabled && !recording) textareaRef.current?.focus();
  }, [disabled, recording]);

  const handleSend = () => {
    if (disabled) return;
    const doneFiles = pendingFiles
      .filter((pf) => pf.status === "done" || pf.status === "pending")
      .map((pf) => pf.file);
    const text = input.trim();
    if (text || doneFiles.length > 0) {
      onSend(text, doneFiles.length > 0 ? doneFiles : undefined);
      setInput("");
      doneFiles.forEach((f) => {
        const pf = pendingFiles.find((p) => p.file === f);
        if (pf?.preview) URL.revokeObjectURL(pf.preview);
      });
      setPendingFiles([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const removeFile = (id: string) => {
    setPendingFiles((prev) => {
      const pf = prev.find((f) => f.id === id);
      if (pf?.preview) URL.revokeObjectURL(pf.preview);
      return prev.filter((f) => f.id !== id);
    });
  };

  const MAX_FILE_SIZE = 20 * 1024 * 1024;

  const handleFilesSelected = async (files: FileList | null) => {
    if (!files) return;

    const validFiles = Array.from(files).filter((f) => {
      if (f.size > MAX_FILE_SIZE) {
        alert(`File "${f.name}" exceeds 20MB limit`);
        return false;
      }
      return true;
    });

    if (validFiles.length === 0) return;

    const newFiles: PendingFile[] = validFiles.map((file) => ({
      id: nextFileId(),
      file,
      preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
      status: "pending" as const,
    }));

    setPendingFiles((prev) => [...prev, ...newFiles]);

    for (const pf of newFiles) {
      const { file } = pf;
      if (file.type.startsWith("audio/")) {
        setPendingFiles((prev) =>
          prev.map((f) => (f.id === pf.id ? { ...f, status: "transcribing" as const } : f))
        );
        setTranscribingAudio(true);
        try {
          const formData = new FormData();
          formData.append("file", file);
          const res = await fetch(`${API}/api/transcribe`, { method: "POST", body: formData });
          if (!res.ok) throw new Error("Transcription failed");
          const data = await res.json();
          if (data.text) {
            setInput((prev) => (prev ? prev + " " + data.text : data.text));
          }
          setPendingFiles((prev) =>
            prev.map((f) => (f.id === pf.id ? { ...f, status: "done" as const } : f))
          );
        } catch {
          setPendingFiles((prev) =>
            prev.map((f) =>
              f.id === pf.id ? { ...f, status: "error" as const, error: "Transcription failed" } : f
            )
          );
        } finally {
          setTranscribingAudio(false);
        }
      } else {
        setPendingFiles((prev) =>
          prev.map((f) => (f.id === pf.id ? { ...f, status: "done" as const } : f))
        );
      }
    }
  };

  const handleVoice = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser. Please use Chrome, Edge, Safari or Firefox.");
      return;
    }

    if (recording) {
      recognitionRef.current?.stop();
      setRecording(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;

      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      // Save baseline text already in input to avoid resetting user edits
      const baseInput = input.trim() ? input.trim() + " " : "";

      recognition.onresult = (event: any) => {
        let interimTranscript = "";
        let finalTranscript = "";

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }

        setInput(baseInput + finalTranscript + interimTranscript);
      };

      recognition.onerror = (e: any) => {
        console.error("Speech recognition error", e);
        setRecording(false);
      };

      recognition.onend = () => {
        setRecording(false);
      };

      recognition.start();
      setRecording(true);
    } catch (err) {
      console.error("Failed to start speech recognition", err);
      setRecording(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      handleFilesSelected(e.dataTransfer.files);
    }
  };

  return (
    <div
      className={`w-full max-w-3xl mx-auto px-6 pb-6 pt-2 shrink-0 ${dragOver ? "opacity-80" : ""}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {pendingFiles.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-2.5">
          {pendingFiles.map((pf) => (
            <div
              key={pf.id}
              className={clsx(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-xl border text-xs shadow-[0_1px_2px_rgba(0,0,0,0.01)]",
                pf.status === "error"
                  ? "bg-red-50 border-red-200 text-red-600"
                  : pf.status === "transcribing"
                  ? "bg-indigo-50 border-indigo-200 text-indigo-600"
                  : "bg-white border-gray-200 text-gray-600"
              )}
            >
              {pf.file.type.startsWith("image/") && pf.preview ? (
                <div className="relative w-8 h-8 rounded-lg overflow-hidden shrink-0">
                  <img
                    src={pf.preview}
                    alt={pf.file.name}
                    className="w-full h-full object-cover"
                  />
                </div>
              ) : pf.file.type.startsWith("audio/") ? (
                <FileAudio className="w-3.5 h-3.5 shrink-0 text-purple-500" />
              ) : (
                <FileText className="w-3.5 h-3.5 shrink-0 text-blue-500" />
              )}
              <span className="truncate max-w-[120px] font-medium">{pf.file.name}</span>
              {pf.status === "transcribing" && <Loader2 className="w-3 h-3 animate-spin shrink-0 text-indigo-500" />}
              {pf.status === "error" && <span className="text-red-500">{pf.error}</span>}
              <button
                onClick={() => removeFile(pf.id)}
                className="p-0.5 hover:bg-black/5 rounded-md shrink-0 transition-colors"
              >
                <X className="w-3.5 h-3.5 text-gray-400 hover:text-gray-600" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div
        className={clsx(
          "flex items-end gap-1.5 bg-white border border-gray-200/80 rounded-2xl px-3.5 py-2.5 shadow-[0_4px_16px_rgba(0,0,0,0.03)] transition-all duration-200",
          disabled ? "opacity-60" : "focus-within:shadow-[0_6px_24px_rgba(0,0,0,0.06)] focus-within:border-indigo-400"
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,audio/*,.pdf,.txt,.md,.csv,.json,.doc,.docx"
          multiple
          className="hidden"
          onChange={(e) => {
            handleFilesSelected(e.target.files);
            e.target.value = "";
          }}
        />

        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors shrink-0 disabled:opacity-40"
          title="Attach files"
        >
          <Plus className="w-5 h-5" />
        </button>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            onInputChange?.(e.target.value);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Message Inquix..."
          rows={1}
          className="flex-1 px-1 py-1.5 resize-none text-sm bg-transparent focus:outline-none text-gray-800 placeholder-gray-400 max-h-[200px]"
          disabled={disabled}
        />

        <div className="flex items-center gap-0.5 shrink-0">
          <button
            onClick={handleVoice}
            disabled={disabled || transcribingAudio}
            className={clsx(
              "p-1.5 rounded-lg transition-colors",
              recording
                ? "bg-red-500 text-white animate-pulse"
                : transcribingAudio
                ? "text-gray-300 cursor-wait"
                : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
            )}
            title={recording ? "Stop recording" : "Voice input"}
          >
            {transcribingAudio ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : recording ? (
              <Square className="w-5 h-5" />
            ) : (
              <Mic className="w-5 h-5" />
            )}
          </button>

          {disabled ? (
            <button
              onClick={onStop}
              className="p-1.5 rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors"
              title="Stop generating"
            >
              <Square className="w-5 h-5" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!hasContent}
              className={clsx(
                "p-1.5 rounded-lg transition-colors",
                hasContent
                  ? "bg-gray-900 text-white hover:bg-gray-800"
                  : "text-gray-400"
              )}
              title="Send message"
            >
              <Send className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      <p className="text-[10px] text-gray-400 text-center mt-2">
        Inquix can make mistakes. Upload documents for RAG, or just ask general questions.
      </p>
    </div>
  );
}
