import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Audiobook",
  description: "Modern AI audiobook generator for documents, notes, and source-grounded audio"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
