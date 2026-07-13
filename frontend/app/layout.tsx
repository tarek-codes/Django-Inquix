import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Inquix — Multi-modal RAG",
  description: "Upload documents and ask questions",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white">{children}</body>
    </html>
  );
}
