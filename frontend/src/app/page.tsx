"use client";

import { useState } from "react";
import { ChatView } from "@/components/chat-view";
import { ConnectionForm } from "@/components/connection-form";
import { MetadataView } from "@/components/metadata-view";
import { PageFooter, WorkspaceHeader, WorkspaceSidebar } from "@/components/workspace-navigation";
import type { WorkspaceView } from "@/components/workspace-navigation";
import type { DatabaseMetadata } from "@/types/database";

export default function Home() {
  const [metadata, setMetadata] = useState<DatabaseMetadata | null>(null);
  const [activeView, setActiveView] = useState<WorkspaceView>("connections");

  function handleConnected(connectionMetadata: DatabaseMetadata) {
    setMetadata(connectionMetadata);
    setActiveView("metadata");
  }

  return (
    <main className="app-shell">
      <WorkspaceSidebar activeView={activeView} metadata={metadata} onNavigate={setActiveView} />

      <section className="main-column" id="main">
        <WorkspaceHeader activeView={activeView} metadata={metadata} onNavigate={setActiveView} />
        <div className="content" id="connect">
          <div hidden={activeView !== "connections"}>
            <ConnectionForm
              onConnected={handleConnected}
              onConnectionStarted={() => setMetadata(null)}
              onProviderChanged={() => setMetadata(null)}
            />
          </div>
          {activeView === "metadata" && metadata && <MetadataView metadata={metadata} />}
          {metadata && (
            <div hidden={activeView !== "chat"}>
              <ChatView connectionName={metadata.connection_name} />
            </div>
          )}
          <PageFooter />
        </div>
      </section>
    </main>
  );
}
