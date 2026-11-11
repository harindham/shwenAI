"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import type { DatabaseConnectionDetails, DatabaseMetadata, Provider } from "@/types/database";
import { DatabaseGlyph, LockGlyph } from "@/components/database-icons";

type ConnectionFormProps = {
  onConnected: (metadata: DatabaseMetadata) => void;
  onConnectionStarted: () => void;
  onProviderChanged: () => void;
};

type ConnectionState = "idle" | "connecting" | "connected" | "error";

export function ConnectionForm({ onConnected, onConnectionStarted, onProviderChanged }: ConnectionFormProps) {
  const [provider, setProvider] = useState<Provider>("postgresql");
  const [schema, setSchema] = useState("public");
  const [port, setPort] = useState("5432");
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [message, setMessage] = useState("");

  function handleProviderChange(nextProvider: Provider) {
    onProviderChanged();
    setProvider(nextProvider);
    setSchema(nextProvider === "postgresql" || nextProvider === "supabase" ? "public" : "");
    setPort(nextProvider === "mysql" || nextProvider === "mariadb" ? "3306" : nextProvider === "other" ? "" : "5432");
    setConnectionState("idle");
    setMessage("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setConnectionState("connecting");
    setMessage("");
    onConnectionStarted();

    const form = new FormData(event.currentTarget);
    const formElement = event.currentTarget;
    const payload: DatabaseConnectionDetails = {
      provider,
      connection_name: String(form.get("connection_name") ?? "").trim(),
      host: String(form.get("host") ?? "").trim(),
      port: Number(form.get("port")),
      database: String(form.get("database") ?? "").trim(),
      schema: provider === "mysql" || provider === "mariadb" ? String(form.get("database") ?? "").trim() : schema.trim(),
      username: String(form.get("username") ?? "").trim(),
      password: String(form.get("password") ?? ""),
      dialect: provider === "other" ? String(form.get("dialect") ?? "").trim() : null,
    };

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiBase}/api/database/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(typeof result.detail === "string" ? result.detail : "Could not connect to the database.");
      }

      const metadata = result as DatabaseMetadata;
      setConnectionState("connected");
      setMessage("Connected. Database metadata has been fetched.");
      onConnected(metadata);

      const passwordInput = formElement.querySelector<HTMLInputElement>("#password");
      if (passwordInput) passwordInput.value = "";
    } catch (error) {
      setConnectionState("error");
      setMessage(error instanceof TypeError
        ? "Can’t reach the FastAPI service. Start the backend and try again."
        : error instanceof Error ? error.message : "Could not connect to the database.");
    }
  }

  return (
    <>
      <div className="heading-row">
        <div>
          <div className="overline"><span /> DATA SOURCES</div>
          <h1>Connect a database</h1>
          <p className="intro">Add a relational database to start exploring your data with shwenAI.</p>
        </div>
        <div className="secure-label"><LockGlyph /> Connection credentials</div>
      </div>

      <div className="content-grid">
        <section className="connection-card" aria-labelledby="details-title">
          <div className="card-heading">
            <div className="card-heading-icon"><DatabaseGlyph /></div>
            <div><h2 id="details-title">Connection details</h2><p>Enter the details for the database you want to connect.</p></div>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="form-section">
              <label className="section-label" htmlFor="provider">Database provider</label>
              <div className="select-wrap">
                <select id="provider" name="provider" value={provider} onChange={(event) => handleProviderChange(event.target.value as Provider)}>
                  <option value="postgresql">PostgreSQL</option>
                  <option value="supabase">Supabase</option>
                  <option value="mysql">MySQL</option>
                  <option value="mariadb">MariaDB</option>
                  <option value="other">Other relational database</option>
                </select>
                <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m5 7.5 5 5 5-5" /></svg>
              </div>
              <p className="field-hint">Choose your database provider. For Supabase, use the connection details from Project Settings.</p>
            </div>

            <div className="form-divider" />
            <div className="form-section">
              <div className="section-title-row"><div><h3>Connection credentials</h3><p>These details are provided by your database host.</p></div><span className="required-legend"><i /> Required</span></div>
              <div className="form-grid">
                <div className="field span-two"><label htmlFor="connection-name">Connection name <span className="required-star">*</span></label><input id="connection-name" name="connection_name" placeholder="e.g. Production analytics" autoComplete="off" maxLength={80} required /><small>Choose a name to identify this connection in your workspace.</small></div>
                <div className="field span-two"><label htmlFor="host">Host <span className="required-star">*</span></label><input id="host" name="host" placeholder="e.g. db.example.com" autoComplete="url" required /><small>Your database server hostname or IP address.</small></div>
                <div className="field"><label htmlFor="port">Port <span className="required-star">*</span></label><input id="port" name="port" type="number" value={port} onChange={(event) => setPort(event.target.value)} min="1" max="65535" required /></div>
                <div className="field"><label htmlFor="database">Database <span className="required-star">*</span></label><input id="database" name="database" placeholder="Database name" required /></div>
                {provider === "mysql" || provider === "mariadb"
                  ? <div className="field span-two"><small>The selected database is the schema for this provider. Metadata will be fetched from that database only.</small></div>
                  : <div className="field span-two"><label htmlFor="schema">Schema <span className="required-star">*</span></label><input id="schema" name="schema" value={schema} onChange={(event) => setSchema(event.target.value)} placeholder="e.g. public" required /><small>Only metadata from this schema will be fetched.</small></div>}
                <div className="field"><label htmlFor="username">Username <span className="required-star">*</span></label><input id="username" name="username" placeholder="Database user" autoComplete="username" required /></div>
                <div className="field"><label htmlFor="password">Password <span className="required-star">*</span></label><input id="password" name="password" type="password" placeholder="Database password" autoComplete="current-password" required /></div>
                {provider === "other" && <div className="field span-two"><label htmlFor="dialect">SQLAlchemy dialect <span className="required-star">*</span></label><input id="dialect" name="dialect" placeholder="e.g. mssql+pyodbc" required /><small>The matching Python database driver must be installed on the API server.</small></div>}
              </div>
            </div>

            <div className="form-divider action-divider" />
            <div className="form-actions"><span className="required-footnote"><span className="required-star">*</span> Required fields</span><div className="action-buttons"><button className="cancel-button" type="button">Cancel</button><button className="connect-button" type="submit" disabled={connectionState === "connecting"}>{connectionState === "connecting" ? <><span className="loading-spinner" />Fetching metadata…</> : <>Connect database <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h12M10 4l6 6-6 6" /></svg></>}</button></div></div>
          </form>
          {message && <div className={`connection-message message-${connectionState}`} role="status" aria-live="polite"><span className="message-icon">{connectionState === "connected" ? "✓" : connectionState === "connecting" ? "·" : "!"}</span><span>{message}</span></div>}
        </section>

        <aside className="side-rail">
          <section className="guide-card">
            <span className="guide-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.8 5.7L20 11l-6.2 2.3L12 19l-1.8-5.7L4 11l6.2-2.3L12 3Z" /><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z" /></svg></span>
            <h3>Where do I find these?</h3>
            <p>Your database provider has these details in its connection or networking settings.</p>
            <div className="guide-rule" />
            <div className="guide-step"><span>01</span><p>Choose your database provider above.</p></div>
            <div className="guide-step"><span>02</span><p>Copy the host, port, and database name from its dashboard.</p></div>
            <div className="guide-step"><span>03</span><p>Use a dedicated database user with only the access you need.</p></div>
          </section>
          <section className="help-card" id="help"><span className="help-card-icon">?</span><div><h3>Need help connecting?</h3><p>Check your provider’s connection guide and network access settings.</p></div><span className="help-chevron">↗</span></section>
          <div className="privacy-note"><LockGlyph /><span>Keep your database credentials private.</span></div>
        </aside>
      </div>
    </>
  );
}
