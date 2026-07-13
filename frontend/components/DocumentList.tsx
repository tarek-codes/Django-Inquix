"use client";
import { FileText, FileImage, Music, File, Trash2 } from "lucide-react";
import type { Document as Doc } from "@/types";

const typeIcons: Record<string, React.ReactNode> = {
  text: <FileText className="w-4 h-4" />,
  pdf: <FileText className="w-4 h-4" />,
  image: <FileImage className="w-4 h-4" />,
  audio: <Music className="w-4 h-4" />,
};

const typeColors: Record<string, string> = {
  text: "text-blue-500",
  pdf: "text-red-500",
  image: "text-green-500",
  audio: "text-purple-500",
};

const statusBadge: Record<string, string> = {
  uploading: "bg-gray-100 text-gray-600",
  processing: "bg-yellow-100 text-yellow-700",
  ready: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

function formatSize(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface DocumentListProps {
  documents: Doc[];
  onDelete: (id: string) => void;
}

export function DocumentList({ documents, onDelete }: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <div className="py-8 text-center">
        <File className="w-8 h-8 text-gray-300 mx-auto mb-2" />
        <p className="text-sm text-gray-400">No documents yet</p>
        <p className="text-xs text-gray-400 mt-1">Upload files to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-gray-400 uppercase tracking-wider px-1 mb-2">
        Documents ({documents.length})
      </p>
      {documents.map((doc) => (
        <div
          key={doc.id}
          className="flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-gray-100 group transition-colors"
        >
          <span className={typeColors[doc.source_type] || "text-gray-400"}>
            {typeIcons[doc.source_type] || <File className="w-4 h-4" />}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-800 truncate">{doc.filename}</p>
            <div className="flex items-center gap-2">
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${statusBadge[doc.status] || statusBadge.processing}`}>
                {doc.status}
              </span>
              {doc.file_size && (
                <span className="text-[10px] text-gray-400">{formatSize(doc.file_size)}</span>
              )}
            </div>
          </div>
          <button
            onClick={() => onDelete(doc.id)}
            className="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
