"use client";
import { FileText, FileImage, Music, File, Trash2, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import type { Document as Doc } from "@/types";

const typeIcons: Record<string, React.ReactNode> = {
  text: <FileText className="w-4.5 h-4.5" />,
  pdf: <FileText className="w-4.5 h-4.5" />,
  doc: <FileText className="w-4.5 h-4.5" />,
  docx: <FileText className="w-4.5 h-4.5" />,
  image: <FileImage className="w-4.5 h-4.5" />,
  audio: <Music className="w-4.5 h-4.5" />,
};

const typeColors: Record<string, string> = {
  text: "text-blue-600",
  pdf: "text-red-600",
  doc: "text-blue-600",
  docx: "text-blue-600",
  image: "text-emerald-600",
  audio: "text-purple-600",
};

const typeBgColors: Record<string, string> = {
  text: "bg-blue-50/80",
  pdf: "bg-red-50/80",
  doc: "bg-blue-50/80",
  docx: "bg-blue-50/80",
  image: "bg-emerald-50/80",
  audio: "bg-purple-50/80",
};

const statusTextColors: Record<string, string> = {
  uploading: "text-gray-500",
  processing: "text-amber-600",
  ready: "text-green-600",
  failed: "text-red-600",
};

function formatSize(bytes: number | null): string {
  if (!bytes) return "0 B";
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
      <div className="py-12 text-center border border-dashed border-gray-200 rounded-xl bg-gray-50/50">
        <File className="w-10 h-10 text-gray-300 mx-auto mb-3" />
        <p className="text-sm font-medium text-gray-600">No documents uploaded</p>
        <p className="text-xs text-gray-400 mt-1 max-w-[200px] mx-auto leading-relaxed">
          Upload PDFs, Word files, images, or audio files to index
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1 shrink-0">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Sources ({documents.length})
        </p>
      </div>
      
      <div className="grid grid-cols-1 gap-2.5">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="relative bg-white border border-gray-200/80 rounded-xl p-3 flex flex-col justify-between hover:border-indigo-400 hover:shadow-[0_4px_12px_rgba(0,0,0,0.04)] transition-all duration-200 group"
          >
            <div className="flex items-start gap-3">
              <div className={`p-2 rounded-lg shrink-0 ${typeBgColors[doc.source_type] || "bg-gray-50"} ${typeColors[doc.source_type] || "text-gray-500"}`}>
                {typeIcons[doc.source_type] || <File className="w-4.5 h-4.5" />}
              </div>
              <div className="flex-1 min-w-0">
                <p 
                  className="text-xs font-semibold text-gray-800 truncate select-all cursor-pointer hover:text-indigo-600" 
                  title={doc.filename}
                >
                  {doc.filename}
                </p>
                <p className="text-[10px] text-gray-400 mt-0.5">{formatSize(doc.file_size)}</p>
              </div>
            </div>
            
            <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-50">
              <div className="flex items-center gap-1.5">
                {doc.status === "ready" ? (
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                ) : doc.status === "failed" ? (
                  <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-500" />
                )}
                <span className={`text-[10px] font-medium capitalize ${statusTextColors[doc.status] || "text-gray-500"}`}>
                  {doc.status}
                </span>
              </div>
              
              <button
                onClick={() => onDelete(doc.id)}
                className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-150 shrink-0"
                title="Delete source"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
