import { BrandMark } from "@/components/database-icons";

type ChatViewProps = {
  connectionName: string;
};

export function ChatView({ connectionName }: ChatViewProps) {
  return (
    <section className="chat-window" aria-labelledby="chat-title">
      <header className="chat-header">
        <div className="chat-header-icon"><ChatGlyph /></div>
        <div><h1 id="chat-title">Chat with your data</h1><p>Connected to <strong>{connectionName}</strong></p></div>
        <span className="chat-ready"><i /> Ready</span>
      </header>

      <div className="chat-conversation" aria-label="Conversation">
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

        <SuggestedPrompts />
      </div>

      <MessageComposer />
    </section>
  );
}

function SuggestedPrompts() {
  const prompts = [
    "What tables are available?",
    "Summarize this database",
    "Show me key relationships",
  ];

  return (
    <div className="suggested-prompts">
      <span>TRY ASKING</span>
      <div>{prompts.map((prompt) => <button key={prompt} type="button">{prompt}</button>)}</div>
    </div>
  );
}

function MessageComposer() {
  return (
    <div className="chat-composer-area">
      <div className="chat-composer">
        <textarea aria-label="Message" placeholder="Ask a question about your data…" rows={1} />
        <button type="button" className="send-message-button" aria-label="Send message" disabled><ChatSendGlyph /></button>
      </div>
      <p>AI responses can be inaccurate. Review important information.</p>
    </div>
  );
}

function ChatGlyph() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H6l-3 2v-6.5A7.5 7.5 0 1 1 20 11.5Z" /><path d="M8 11h8M8 14.5h5" /></svg>;
}

function ChatSendGlyph() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 11 16-7-7 16-2-7-7-2Z" /><path d="m11 13 4-4" /></svg>;
}
