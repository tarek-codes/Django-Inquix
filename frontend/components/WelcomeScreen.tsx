"use client";
import { Brain, Sparkles } from "lucide-react";

const suggestions = [
  "What documents are available in this knowledge base?",
  "Summarize the key information from my documents",
  "Search the web for recent developments in AI",
  "What can you tell me about the uploaded content?",
];

interface WelcomeScreenProps {
  onSuggestionClick: (text: string) => void;
}

export function WelcomeScreen({ onSuggestionClick }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-10">
      <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 mb-5 shadow-lg shadow-indigo-200">
        <Brain className="w-7 h-7 text-white" />
      </div>
      <h1 className="text-2xl font-semibold text-gray-800 mb-1">Inquix</h1>
      <p className="text-sm text-gray-400 mb-8 text-center max-w-md">
        Ask anything about your documents, search the web, or just chat
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-lg">
        {suggestions.map((text) => (
          <button
            key={text}
            onClick={() => onSuggestionClick(text)}
            className="flex items-center gap-2.5 px-4 py-3 text-xs text-left text-gray-600 bg-white border border-gray-200 rounded-xl hover:border-indigo-300 hover:bg-indigo-50/40 hover:text-indigo-700 transition-all shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span className="leading-snug">{text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
