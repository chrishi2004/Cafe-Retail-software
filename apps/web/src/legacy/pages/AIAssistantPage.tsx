import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Database,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
} from "lucide-react";

import { getAISession, listAISessions, sendAIChatMessage } from "../api/ai";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingState, MetricCard } from "../components/ui";
import type { AIChatMessage, AIChatSession, AIToolCall } from "../types";
import { formatStatus } from "../utils/format";

const SUGGESTED_QUESTIONS = [
  "What are today's sales?",
  "Which products are low in stock?",
  "Which items should I reorder today?",
  "What are the top-selling products this month?",
  "Which branch performed best?",
  "Which products are slow-moving?",
  "Summarize pending purchase orders.",
  "Forecast next week's demand.",
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Could not reach the AI assistant API. Check that the backend is running.";
}

function metadataToolCalls(message: AIChatMessage): AIToolCall[] {
  const calls = message.metadata_json?.tool_calls;
  if (!Array.isArray(calls)) {
    return [];
  }
  return calls.filter((call): call is AIToolCall => {
    return (
      typeof call === "object" &&
      call !== null &&
      "name" in call &&
      typeof (call as { name?: unknown }).name === "string"
    );
  });
}

function metadataFlag(message: AIChatMessage, key: string): boolean {
  return message.metadata_json?.[key] === true;
}

function metadataText(message: AIChatMessage, key: string): string | null {
  const value = message.metadata_json?.[key];
  return typeof value === "string" ? value : null;
}

function toolLabel(toolName: string): string {
  return formatStatus(toolName.replace(/^get_/, ""));
}

function dateTime(value: string): string {
  return new Date(value).toLocaleString([], {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AIAssistantPage() {
  const { token } = useAuth();
  const [sessions, setSessions] = useState<AIChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AIChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingSession, setLoadingSession] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const latestAssistantMessage = useMemo(() => {
    return [...messages].reverse().find((message) => message.sender === "assistant") ?? null;
  }, [messages]);

  const latestTools = useMemo(() => {
    return latestAssistantMessage ? metadataToolCalls(latestAssistantMessage) : [];
  }, [latestAssistantMessage]);

  const loadSessions = useCallback(async () => {
    if (!token) return;
    setLoadingSessions(true);
    setError(null);
    try {
      setSessions(await listAISessions(token));
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoadingSessions(false);
    }
  }, [token]);

  const loadSessionDetail = useCallback(
    async (sessionId: number) => {
      if (!token) return;
      setLoadingSession(true);
      setError(null);
      try {
        const detail = await getAISession(token, sessionId);
        setActiveSessionId(detail.id);
        setMessages(detail.messages);
      } catch (loadError) {
        setError(errorMessage(loadError));
      } finally {
        setLoadingSession(false);
      }
    },
    [token],
  );

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const startNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    setInput("");
    setError(null);
  };

  const sendMessage = async (messageText: string) => {
    const trimmed = messageText.trim();
    if (!token || !trimmed || sending) return;

    setSending(true);
    setError(null);
    try {
      const response = await sendAIChatMessage(token, {
        message: trimmed,
        session_id: activeSessionId,
      });
      setActiveSessionId(response.session_id);
      setMessages((current) => [...current, response.user_message, response.assistant_message]);
      setInput("");
      await loadSessions();
    } catch (sendError) {
      setError(errorMessage(sendError));
    } finally {
      setSending(false);
    }
  };

  return (
    <section className="page-stack" aria-labelledby="ai-title">
      <div className="page-header">
        <div>
          <p className="eyebrow">Business assistant</p>
          <h2 id="ai-title">AI assistant</h2>
          <p className="page-description">
            Ask operational questions about sales, stock, reorder decisions, purchase orders, and forecasts.
          </p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">Tool-backed answers</span>
          <div className="page-actions">
            <button className="action-button secondary" onClick={() => void loadSessions()} type="button">
              <RefreshCw aria-hidden="true" size={16} />
              Refresh
            </button>
            <button className="action-button primary" onClick={startNewChat} type="button">
              <Plus aria-hidden="true" size={16} />
              New chat
            </button>
          </div>
        </div>
      </div>

      <section className="metric-grid">
        <MetricCard
          metric={{
            label: "Mode",
            value: "Read-only",
            detail: "Operational writes require confirmation",
            tone: "blue",
          }}
        />
        <MetricCard
          metric={{
            label: "Tools",
            value: "7 connected",
            detail: "Sales, stock, orders, forecast, reorder",
            tone: "green",
          }}
        />
        <MetricCard
          metric={{
            label: "Provider",
            value: "Configurable",
            detail: "Deterministic fallback when no key exists",
            tone: "slate",
          }}
        />
        <MetricCard
          metric={{
            label: "Guardrails",
            value: "Active",
            detail: "No invented numbers or silent writes",
            tone: "amber",
          }}
        />
      </section>

      {error ? <ErrorState message={error} title="AI assistant error" /> : null}

      <section className="ai-grid">
        <aside className="panel ai-session-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">History</p>
              <h3>Chat sessions</h3>
            </div>
          </div>
          {loadingSessions ? <LoadingState label="Loading sessions" /> : null}
          {!loadingSessions && sessions.length === 0 ? (
            <EmptyState title="No saved chats" message="Start with a suggested business question." />
          ) : null}
          {!loadingSessions && sessions.length > 0 ? (
            <div className="ai-session-list">
              {sessions.map((session) => (
                <button
                  className={session.id === activeSessionId ? "active" : ""}
                  key={session.id}
                  onClick={() => void loadSessionDetail(session.id)}
                  type="button"
                >
                  <MessageSquare aria-hidden="true" size={16} />
                  <span>
                    <strong>{session.title}</strong>
                    <b>{dateTime(session.updated_at)}</b>
                  </span>
                </button>
              ))}
            </div>
          ) : null}
        </aside>

        <article className="panel ai-chat-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Assistant workspace</p>
              <h3>{activeSessionId ? `Session #${activeSessionId}` : "New business question"}</h3>
            </div>
            <span className="status-badge ok">
              <ShieldCheck aria-hidden="true" size={14} />
              RBAC enforced
            </span>
          </div>

          <div className="ai-suggestions" aria-label="Suggested AI questions">
            {SUGGESTED_QUESTIONS.map((question) => (
              <button disabled={sending} key={question} onClick={() => void sendMessage(question)} type="button">
                {question}
              </button>
            ))}
          </div>

          <div className="ai-message-list" aria-live="polite">
            {loadingSession ? <LoadingState label="Loading chat" /> : null}
            {!loadingSession && messages.length === 0 ? (
              <EmptyState title="No messages yet" message="Ask a business question to query the local database." />
            ) : null}
            {!loadingSession
              ? messages.map((message) => {
                  const tools = metadataToolCalls(message);
                  const requiresConfirmation = metadataFlag(message, "requires_confirmation");
                  const suggestedAction = metadataText(message, "suggested_action");
                  return (
                    <article className={`ai-message ${message.sender}`} key={message.id}>
                      <div className="ai-avatar">
                        {message.sender === "assistant" ? <Bot aria-hidden="true" size={16} /> : "You"}
                      </div>
                      <div className="ai-message-body">
                        <p>{message.message}</p>
                        {tools.length > 0 ? (
                          <div className="ai-tool-row">
                            {tools.map((tool) => (
                              <span key={`${message.id}-${tool.name}`}>
                                <Database aria-hidden="true" size={13} />
                                {toolLabel(tool.name)}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {requiresConfirmation ? (
                          <div className="ai-confirmation">
                            <AlertTriangle aria-hidden="true" size={16} />
                            <span>{suggestedAction ?? "Confirmation required before any write action."}</span>
                          </div>
                        ) : null}
                        <time>{dateTime(message.created_at)}</time>
                      </div>
                    </article>
                  );
                })
              : null}
            {sending ? (
              <article className="ai-message assistant">
                <div className="ai-avatar">
                  <Bot aria-hidden="true" size={16} />
                </div>
                <div className="ai-message-body">
                  <p>Checking backend tools...</p>
                </div>
              </article>
            ) : null}
          </div>

          <form
            className="ai-input-row"
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage(input);
            }}
          >
            <textarea
              aria-label="Ask the AI assistant"
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about sales, stock, reorders, purchase orders, or forecasts"
              value={input}
            />
            <button className="action-button primary" disabled={sending || input.trim().length === 0} type="submit">
              <Send aria-hidden="true" size={16} />
              Send
            </button>
          </form>
        </article>

        <aside className="panel ai-tool-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Latest tool path</p>
              <h3>Database calls</h3>
            </div>
          </div>
          {latestTools.length === 0 ? (
            <EmptyState title="No tool call yet" message="The next assistant answer will show the backend tool used." />
          ) : (
            <div className="ai-tool-list">
              {latestTools.map((tool) => (
                <article key={tool.name}>
                  <div>
                    <Database aria-hidden="true" size={16} />
                    <strong>{toolLabel(tool.name)}</strong>
                  </div>
                  <p>{tool.description}</p>
                </article>
              ))}
            </div>
          )}
        </aside>
      </section>
    </section>
  );
}
