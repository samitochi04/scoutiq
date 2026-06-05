import { useState, useCallback } from "react";

const STORAGE_KEY = "scoutiq_conversations";
const MAX_CONVERSATIONS = 50;

function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveConversations(conversations) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch {
    // Storage full — remove oldest
    try {
      const trimmed = conversations.slice(-30);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    } catch {}
  }
}

export function useConversations() {
  const [conversations, setConversations] = useState(() => loadConversations());

  const addConversation = useCallback((entry) => {
    setConversations((prev) => {
      const next = [entry, ...prev].slice(0, MAX_CONVERSATIONS);
      saveConversations(next);
      return next;
    });
  }, []);

  const updateConversation = useCallback((id, updates) => {
    setConversations((prev) => {
      const next = prev.map((c) => (c.id === id ? { ...c, ...updates } : c));
      saveConversations(next);
      return next;
    });
  }, []);

  const deleteConversation = useCallback((id) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      saveConversations(next);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setConversations([]);
  }, []);

  return {
    conversations,
    addConversation,
    updateConversation,
    deleteConversation,
    clearAll,
  };
}
