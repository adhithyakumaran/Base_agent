import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

const body = Inter({
  subsets: ["latin"],
  variable: "--font-body-fallback",
});

const display = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display-fallback",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono-fallback",
});

export const metadata: Metadata = {
  title: "ScoutAI · Enterprise QA Console",
  description: "Run approved QA flows, inspect evidence, and verify results.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${body.variable} ${display.variable} ${mono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
