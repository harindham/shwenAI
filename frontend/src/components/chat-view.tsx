"use client";

import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { BrandMark } from "@/components/database-icons";

type ChatViewProps = {
  connectionName: string;
};

type QueryResult = {
  query: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
};

function isQueryResult(value: unknown): value is QueryResult {
  if (typeof value !== "object" || value === null) return false;
  const result = value as Record<string, unknown>;
  return typeof result.query === "string"
    && Array.isArray(result.columns) && result.columns.every((column) => typeof column === "string")
    && Array.isArray(result.rows) && result.rows.every((row) => Array.isArray(row))
    && typeof result.row_count === "number" && Number.isInteger(result.row_count) && result.row_count >= 0
    && typeof result.truncated === "boolean";
}

export function ChatView({ connectionName }: ChatViewProps) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; text: string; result?: QueryResult }[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function sendMessage(messageText: string) {
    const message = messageText.trim();
    if (!message || sending) return;

    setSending(true);
    setError("");
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiBase}/api/chat/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ connection_name: connectionName, message }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(typeof result.detail === "string" ? result.detail : "Could not send message.");
      }

      const assistantResponse: unknown = result.response;
      if (typeof assistantResponse !== "string" && !isQueryResult(assistantResponse)) {
        throw new Error("The server returned an invalid query result. Please try again.");
      }

      setMessages((currentMessages) => [
        ...currentMessages,
        { role: "user", text: message },
        typeof assistantResponse === "string"
          ? { role: "assistant", text: assistantResponse }
          : { role: "assistant", text: `${assistantResponse.row_count} rows returned`, result: assistantResponse },
      ]);
      setDraft("");
    } catch (sendError) {
      setError(sendError instanceof TypeError
        ? "Can’t reach the FastAPI service. Start the backend and try again."
        : sendError instanceof Error ? sendError.message : "Could not send message.");
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(draft);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(draft);
    }
  }

  return (
    <section className="chat-window" aria-labelledby="chat-title">
      <header className="chat-header">
        <div className="chat-header-icon"><ChatGlyph /></div>
        <div><h1 id="chat-title">Chat with your data</h1><p>Connected to <strong>{connectionName}</strong></p></div>
        <span className="chat-ready"><i /> Ready</span>
      </header>

      <div className="chat-conversation" role="region" aria-label="Conversation" tabIndex={0}>
        <div className="chat-date-divider"><span>NEW CONVERSATION</span></div>
        <div className="chat-message-row">
          <div className="assistant-avatar"><BrandMark /></div>
          <div className="chat-message-content">
            <div className="chat-message-author">shwenAI <span>now</span></div>
            <div className="chat-bubble assistant-bubble">
              <p>Let’s chat with your data.</p>
              <p>Ask a question about <strong>{connectionName}</strong> to get started. I can help you explore your database structure and find useful insights.</p>
            </div>
          </div>
        </div>

        {messages.map((message, index) => (
          <div className={`chat-message-row${message.role === "user" ? " user-message-row" : ""}`} key={`${index}-${message.role}-${message.text}`}>
            {message.role === "user" ? <div className="user-avatar">S</div> : <div className="assistant-avatar"><BrandMark /></div>}
            <div className="chat-message-content">
              <div className="chat-message-author">{message.role === "user" ? "You" : "shwenAI"} <span>just now</span></div>
              <div className={`chat-bubble ${message.role === "user" ? "user-bubble" : "assistant-bubble"}`}>
                <MessageContent text={message.text} result={message.result} />
              </div>
            </div>
          </div>
        ))}

        {messages.length === 0 && <SuggestedPrompts onSelect={sendMessage} />}
      </div>

      <MessageComposer
        draft={draft}
        sending={sending}
        error={error}
        onDraftChange={setDraft}
        onKeyDown={handleComposerKeyDown}
        onSubmit={handleSubmit}
      />
    </section>
  );
}

function MessageContent({ text, result }: { text: unknown; result?: unknown }) {
  if (isQueryResult(result)) return <QueryResultView result={result} />;
  // Fast Refresh can preserve messages from when responses were stored in text.
  if (isQueryResult(text)) return <QueryResultView result={text} />;
  return <>{typeof text === "string" ? text : "This message could not be displayed. Please send it again."}</>;
}

function QueryResultView({ result }: { result: QueryResult }) {
  return (
    <div className="query-result">
      <details><summary>SQL query</summary><pre>{result.query}</pre></details>
      <p>{result.row_count} {result.row_count === 1 ? "row" : "rows"} returned{result.truncated ? " (showing the first 1,000 rows)" : ""}.</p>
      {result.rows.length === 0 ? <p>No matching rows.</p> : (
        <div className="query-result-scroll" role="region" aria-label="Query results" tabIndex={0}>
          <table>
            <thead><tr>{result.columns.map((column, index) => <th key={index} scope="col">{column}</th>)}</tr></thead>
            <tbody>{result.rows.map((row, rowIndex) => (
              <tr key={rowIndex}>{row.map((value, columnIndex) => (
                <td key={columnIndex}>{value === null ? "NULL" : typeof value === "object" ? JSON.stringify(value) : String(value)}</td>
              ))}</tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SuggestedPrompts({ onSelect }: { onSelect: (prompt: string) => void }) {
  const prompts = [
    "What tables are available?",
    "Summarize this database",
    "Show me key relationships",
  ];

  return (
    <div className="suggested-prompts">
      <span>TRY ASKING</span>
      <div>{prompts.map((prompt) => <button key={prompt} type="button" onClick={() => onSelect(prompt)}>{prompt}</button>)}</div>
    </div>
  );
}

function MessageComposer({
  draft,
  sending,
  error,
  onDraftChange,
  onKeyDown,
  onSubmit,
}: {
  draft: string;
  sending: boolean;
  error: string;
  onDraftChange: (value: string) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="chat-composer-area">
      <form className="chat-composer" onSubmit={onSubmit}>
        <textarea aria-label="Message" placeholder="Ask a question about your data…" rows={1} value={draft} onChange={(event) => onDraftChange(event.target.value)} onKeyDown={onKeyDown} maxLength={4000} />
        <button type="submit" className="send-message-button" aria-label="Send message" disabled={!draft.trim() || sending}>{sending ? <span className="loading-spinner" /> : <ChatSendGlyph />}</button>
      </form>
      {error && <p className="chat-error" role="alert">{error}</p>}
      <p>Press Enter to send · Shift + Enter for a new line</p>
    </div>
  );
}

function ChatGlyph() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H6l-3 2v-6.5A7.5 7.5 0 1 1 20 11.5Z" /><path d="M8 11h8M8 14.5h5" /></svg>;
}

function ChatSendGlyph() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 11 16-7-7 16-2-7-7-2Z" /><path d="m11 13 4-4" /></svg>;
}
