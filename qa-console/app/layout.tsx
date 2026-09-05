import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const body = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Apex QA Agent · Enterprise Console",
  description:
    "Enterprise QA agent console — Groq intent classification, Playwright suite execution, and exportable reports.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${body.variable} antialiased`}>{children}</body>
    </html>
  );
}
