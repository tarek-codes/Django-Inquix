"use client";
import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Plus, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface FileUploadProps {
  kbId: string;
  onUploadComplete: () => void;
}

export function FileUpload({ kbId, onUploadComplete }: FileUploadProps) {
  const [uploading, setUploading] = useState(false);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;
      setUploading(true);
      
      try {
        for (const file of acceptedFiles) {
          await api.uploadDocument(kbId, file);
        }
      } catch (err) {
        console.error("Upload failed", err);
      } finally {
        setUploading(false);
        onUploadComplete();
      }
    },
    [kbId, onUploadComplete]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, disabled: uploading });

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border border-dashed rounded-xl p-4 text-center cursor-pointer transition-all duration-200
          ${isDragActive
            ? "border-indigo-500 bg-indigo-50/50"
            : "border-indigo-200 hover:border-indigo-400 bg-indigo-50/10 hover:bg-indigo-50/30"
          }
          ${uploading ? "opacity-50 pointer-events-none" : ""}`}
      >
        <input {...getInputProps()} />
        {uploading ? (
          <div className="flex flex-col items-center justify-center gap-2 py-1.5 text-xs font-semibold text-indigo-600">
            <Loader2 className="w-5 h-5 animate-spin shrink-0" />
            <span>Analyzing document(s)...</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1.5 py-1">
            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600">
              <Plus className="w-4.5 h-4.5" />
            </div>
            <p className="text-xs font-semibold text-indigo-700">Add source</p>
            <p className="text-[10px] text-indigo-500">PDF, Word, TXT, CSV, MP3, Images</p>
          </div>
        )}
      </div>
    </div>
  );
}
