"use client";

import { BrowserRecorderPanel } from "@/components/browser-recorder";

export function RecorderView() {
  return (
    <div className="view-stack">
      <header className="view-header">
        <div>
          <h1>Recorder</h1>
          <p className="view-subtitle">
            Engineering utility for capturing browser interactions during exploration. Secondary to controlled
            execution workflows.
          </p>
        </div>
      </header>
      <BrowserRecorderPanel />
    </div>
  );
}
