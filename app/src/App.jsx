import { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import QueryHome from "./components/QueryHome";
import ChatView from "./components/ChatView";
import About from "./components/About";
import HistoryView from "./components/HistoryView";
import MobileBottomNav from "./components/MobileBottomNav";
import { useConversations } from "./hooks/useConversations";
import { useAgent } from "./hooks/useAgent";
import "./App.css";

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export default function App() {
  const [view, setView] = useState("home"); // 'home' | 'chat' | 'history'
  const [messages, setMessages] = useState([]);
  const [sessionId] = useState(() => generateId());

  const { conversations, addConversation, deleteConversation, clearAll } =
    useConversations();
  const {
    isLoading,
    streamedReport,
    reasoningSteps,
    similarPlayers,
    confidence,
    error,
    sendQuery,
    cancel,
    reset,
  } = useAgent();

  const handleSubmit = useCallback(
    async (query, mode) => {
      const userMsg = { id: generateId(), role: "user", content: query, mode };
      setMessages((prev) => [...prev, userMsg]);
      setView("chat");
      reset();

      const result = await sendQuery(query, mode, sessionId);
      if (!result) return; // cancelled

      const agentMsg = {
        id: generateId(),
        role: "agent",
        report: result.report,
        reasoning_steps: result.reasoning_steps,
        similar_players: result.similar_players,
        confidence: result.confidence,
        complete: true,
      };

      setMessages((prev) => [...prev, agentMsg]);

      // Save to history
      addConversation({
        id: generateId(),
        timestamp: new Date().toISOString(),
        query,
        mode,
        response: {
          report: result.report,
          reasoning_steps: result.reasoning_steps,
          similar_players: result.similar_players,
          confidence: result.confidence,
        },
      });
    },
    [sendQuery, reset, sessionId, addConversation],
  );

  const handleNewChat = useCallback(() => {
    cancel();
    reset();
    setMessages([]);
    setView("home");
  }, [cancel, reset]);

  const handleHistorySelect = useCallback((conv) => {
    const userMsg = {
      id: generateId(),
      role: "user",
      content: conv.query,
      mode: conv.mode,
    };
    const agentMsg = {
      id: generateId(),
      role: "agent",
      report: conv.response?.report || "",
      reasoning_steps: conv.response?.reasoning_steps || [],
      similar_players: conv.response?.similar_players || [],
      confidence: conv.response?.confidence,
      complete: true,
    };
    setMessages([userMsg, agentMsg]);
    setView("chat");
  }, []);

  const handleNavigate = useCallback(
    (target) => {
      if (target === "home") {
        handleNewChat();
      } else {
        setView(target);
      }
    },
    [handleNewChat],
  );

  return (
    <div className="app-shell">
      <Sidebar activeView={view} onNavigate={handleNavigate} />

      <main className="app-content" role="main">
        {view === "home" && <QueryHome onSubmit={handleSubmit} />}
        {view === "chat" && (
          <ChatView
            messages={messages}
            isLoading={isLoading}
            streamedReport={streamedReport}
            reasoningSteps={reasoningSteps}
            similarPlayers={similarPlayers}
            confidence={confidence}
            error={error}
            onSend={handleSubmit}
            onCancel={cancel}
            onNewChat={handleNewChat}
          />
        )}
        {view === "about" && <About onNewChat={handleNewChat} />}
        {view === "history" && (
          <HistoryView
            conversations={conversations}
            onSelect={handleHistorySelect}
            onDelete={deleteConversation}
            onClear={clearAll}
            onNewChat={handleNewChat}
          />
        )}
      </main>

      <MobileBottomNav activeView={view} onNavigate={handleNavigate} />
    </div>
  );
}
