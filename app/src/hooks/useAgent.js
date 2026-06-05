import { useState, useRef, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "";

export function useAgent() {
  const [isLoading, setIsLoading] = useState(false);
  const [streamedReport, setStreamedReport] = useState("");
  const [reasoningSteps, setReasoningSteps] = useState([]);
  const [similarPlayers, setSimilarPlayers] = useState([]);
  const [confidence, setConfidence] = useState(null);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const reset = useCallback(() => {
    setStreamedReport("");
    setReasoningSteps([]);
    setSimilarPlayers([]);
    setConfidence(null);
    setError(null);
  }, []);

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setIsLoading(false);
    }
  }, []);

  const sendQuery = useCallback(async (query, mode, sessionId) => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setStreamedReport("");
    setReasoningSteps([]);
    setSimilarPlayers([]);
    setConfidence(null);
    setError(null);

    let fullReport = "";
    let finalConfidence = "MEDIUM";
    let finalSimilarPlayers = [];
    let finalReasoningSteps = [];

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, mode, session_id: sessionId }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep incomplete line

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr || jsonStr === "[DONE]") continue;

          try {
            const event = JSON.parse(jsonStr);

            if (event.type === "thinking") {
              finalReasoningSteps = [...finalReasoningSteps, event];
              setReasoningSteps([...finalReasoningSteps]);
            } else if (event.type === "token") {
              fullReport += event.content;
              setStreamedReport(fullReport);
            } else if (event.type === "similar") {
              finalSimilarPlayers = event.players || [];
              setSimilarPlayers(finalSimilarPlayers);
            } else if (event.type === "done") {
              finalConfidence = event.confidence || "MEDIUM";
              setConfidence(finalConfidence);
              if (event.report) {
                fullReport = event.report;
                setStreamedReport(fullReport);
              }
              if (event.similar_players) {
                finalSimilarPlayers = event.similar_players;
                setSimilarPlayers(finalSimilarPlayers);
              }
            }
          } catch {}
        }
      }

      // Finalize
      if (!finalConfidence) setConfidence("MEDIUM");
    } catch (err) {
      if (err.name === "AbortError") return null;
      setError(err.message || "Something went wrong. Please try again.");
      console.error("Agent error:", err);
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }

    return {
      report: fullReport,
      reasoning_steps: finalReasoningSteps,
      similar_players: finalSimilarPlayers,
      confidence: finalConfidence,
    };
  }, []);

  return {
    isLoading,
    streamedReport,
    reasoningSteps,
    similarPlayers,
    confidence,
    error,
    sendQuery,
    cancel,
    reset,
  };
}
