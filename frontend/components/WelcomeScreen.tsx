"use client";
import { BookOpen, FileText, HelpCircle, Headphones, Sparkles, Brain } from "lucide-react";

interface GuideCard {
  title: string;
  description: string;
  prompt: string;
  icon: React.ReactNode;
  color: string;
}

const guideCards: GuideCard[] = [
  {
    title: "Briefing Document",
    description: "Generate a structured briefing summary of all your uploaded sources.",
    prompt: "Create a briefing document based on my uploaded sources, detailing key themes, facts, and conclusions.",
    icon: <FileText className="w-5 h-5" />,
    color: "bg-blue-50 text-blue-600 border-blue-100 hover:border-blue-300",
  },
  {
    title: "FAQ Document",
    description: "Generate a list of frequently asked questions and detailed answers.",
    prompt: "Generate a comprehensive FAQ document based on the uploaded sources.",
    icon: <HelpCircle className="w-5 h-5" />,
    color: "bg-emerald-50 text-emerald-600 border-emerald-100 hover:border-emerald-300",
  },
  {
    title: "Study Guide",
    description: "Create a study guide with key concepts, essay prompts, and a glossary.",
    prompt: "Generate a comprehensive study guide based on the uploaded sources, including key concepts, study questions, and glossary terms.",
    icon: <BookOpen className="w-5 h-5" />,
    color: "bg-amber-50 text-amber-600 border-amber-100 hover:border-amber-300",
  },
  {
    title: "Audio Overview Script",
    description: "Draft a conversational podcast-style discussion between two hosts analyzing the files.",
    prompt: "Generate a conversational podcast style audio overview script between two hosts analyzing the uploaded sources in an engaging way.",
    icon: <Headphones className="w-5 h-5" />,
    color: "bg-purple-50 text-purple-600 border-purple-100 hover:border-purple-300",
  },
];

const suggestions = [
  "Summarize the key information from my documents",
  "Search the web for recent developments in AI",
];

interface WelcomeScreenProps {
  onSuggestionClick: (text: string) => void;
}

export function WelcomeScreen({ onSuggestionClick }: WelcomeScreenProps) {
  return (
    <div className="flex-1 flex flex-col justify-center px-6 lg:px-16 py-10 max-w-4xl mx-auto w-full">
      {/* Brand Hero */}
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md">
          <Brain className="w-5.5 h-5.5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-800 tracking-tight">Inquix</h1>
          <p className="text-xs text-gray-400">Interactive RAG Notebook Workspace</p>
        </div>
      </div>

      {/* Guide Header */}
      <div className="mb-6">
        <h2 className="text-base font-semibold text-gray-800">Notebook guide</h2>
        <p className="text-xs text-gray-400 mt-0.5">Use these templates to quickly synthesize your sources</p>
      </div>

      {/* Guide Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {guideCards.map((card) => (
          <button
            key={card.title}
            onClick={() => onSuggestionClick(card.prompt)}
            className={`flex items-start gap-4 p-4 text-left bg-white border border-gray-200/80 rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.01)] hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 group`}
          >
            <div className={`p-2.5 rounded-xl shrink-0 ${card.color.split(" ")[0]} ${card.color.split(" ")[1]}`}>
              {card.icon}
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-800 group-hover:text-indigo-600 transition-colors">
                {card.title}
              </h3>
              <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                {card.description}
              </p>
            </div>
          </button>
        ))}
      </div>

      {/* Suggested Questions */}
      <div className="space-y-3">
        <div className="flex items-center gap-1.5 px-1">
          <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Suggested Queries</h3>
        </div>
        
        <div className="flex flex-wrap gap-2">
          {suggestions.map((text) => (
            <button
              key={text}
              onClick={() => onSuggestionClick(text)}
              className="px-4 py-2 text-xs text-gray-600 bg-white border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/20 hover:text-indigo-700 transition-all rounded-full shadow-[0_1px_3px_rgba(0,0,0,0.01)]"
            >
              {text}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
