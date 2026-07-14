"use client";
import { X, Loader2 } from "lucide-react";
import { FileUpload } from "./FileUpload";
import { DocumentList } from "./DocumentList";
import type { Document as Doc } from "@/types";

interface DocumentPanelProps {
  kbId: string;
  documents: Doc[];
  isOpen: boolean;
  onClose: () => void;
  onUploadComplete: () => void;
  onDeleteDocument: (id: string) => void;
}

export function DocumentPanel({
  kbId,
  documents,
  isOpen,
  onClose,
  onUploadComplete,
  onDeleteDocument,
}: DocumentPanelProps) {
  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 bg-black/20 z-30" onClick={onClose} />
      )}

      <div
        className={`
          fixed top-0 right-0 h-full w-80 bg-white shadow-xl z-40
          transform transition-transform duration-300 ease-in-out
          ${isOpen ? "translate-x-0" : "translate-x-full"}
          flex flex-col
        `}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 shrink-0">
          <h2 className="text-sm font-semibold text-gray-800">Documents</h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-3 border-b border-gray-100">
          <FileUpload kbId={kbId} onUploadComplete={onUploadComplete} />
        </div>

        <div className="flex-1 overflow-y-auto px-3 pb-3">
          <DocumentList documents={documents} onDelete={onDeleteDocument} />
        </div>
      </div>
    </>
  );
}
