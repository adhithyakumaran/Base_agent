"use client";

import { SettingsPanel, DeliveryInbox } from "@/components/settings-panel";

export function ConnectorsView() {
  return (
    <div className="view-stack">
      <header className="view-header">
        <div>
          <h1>Connectors & policy</h1>
          <p className="view-subtitle">
            Environment, credentials, notifications, agent policy, execution, and integrations
          </p>
        </div>
      </header>

      <div className="settings-grid">
        <SettingsPanel />
        <DeliveryInbox />
      </div>
    </div>
  );
}
