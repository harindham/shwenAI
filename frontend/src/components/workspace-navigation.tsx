import { BrandMark, DatabaseGlyph } from "@/components/database-icons";
import type { DatabaseMetadata } from "@/types/database";

export type WorkspaceView = "connections" | "metadata" | "chat";

type WorkspaceNavigationProps = {
  activeView: WorkspaceView;
  metadata: DatabaseMetadata | null;
  onNavigate: (view: WorkspaceView) => void;
};

export function WorkspaceSidebar({ activeView, metadata, onNavigate }: WorkspaceNavigationProps) {
  return (
    <aside className="sidebar">
      <a className="brand" href="#main"><BrandMark /><span>shwen<span className="brand-accent">AI</span></span></a>
      <div className="nav-caption">WORKSPACE</div>
      <nav className="navigation" aria-label="Workspace">
        <button className={`nav-link${activeView === "connections" ? " active" : ""}`} type="button" onClick={() => onNavigate("connections")}><DatabaseGlyph /><span>Connections</span></button>
        {metadata && <div className="connection-nav-group">
          <div className="connection-nav-name"><DatabaseGlyph /><span>{metadata.connection_name}</span></div>
          <button className={`nav-link connection-nav-link${activeView === "metadata" ? " active" : ""}`} type="button" onClick={() => onNavigate("metadata")}><span className="connection-nav-dot" /><span>Fetched metadata</span></button>
          <button className={`nav-link connection-nav-link${activeView === "chat" ? " active" : ""}`} type="button" onClick={() => onNavigate("chat")}><span className="connection-nav-dot" /><span>Chat</span></button>
        </div>}
      </nav>
      <div className="sidebar-bottom">
        <a className="help-link" href="#help"><span className="help-mark">?</span><span>Help center</span><span className="external-mark">↗</span></a>
        <div className="account-row"><span className="avatar">S</span><span className="account-copy"><strong>My workspace</strong><small>Free plan</small></span><button className="more-button" type="button" aria-label="More workspace options">···</button></div>
      </div>
    </aside>
  );
}

export function WorkspaceHeader({ activeView, metadata, onNavigate }: WorkspaceNavigationProps) {
  return (
    <header className="topbar">
      <div className="breadcrumbs">
        <span>Workspace</span><span className="crumb-slash">/</span>
        <button type="button" onClick={() => onNavigate("connections")}>Connections</button>
        {activeView !== "connections" && metadata && <><span className="crumb-slash">/</span><span>{metadata.connection_name}</span><span className="crumb-slash">/</span><strong>{activeView === "chat" ? "Chat" : "Fetched metadata"}</strong></>}
      </div>
      <div className="topbar-right"><span className="online-indicator"><i />Workspace ready</span><button className="profile-avatar" type="button" aria-label="Account menu">S</button></div>
    </header>
  );
}

export function PageFooter() {
  return <footer className="page-footer"><span>© 2026 shwenAI</span><span>Connect your data, thoughtfully <i>✳</i></span></footer>;
}
