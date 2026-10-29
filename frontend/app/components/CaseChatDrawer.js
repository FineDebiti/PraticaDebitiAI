"use client";
import { useState, useEffect, useRef } from "react";
import { getCaseChat, sendCaseChatMessage, clearCaseChat } from "../api";

export default function CaseChatDrawer({
  caseId,
  clientName,
  isOpen,
  onClose,
  onApplyInstruction,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [fetchingHistory, setFetchingHistory] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (!caseId || !isOpen) return;
    setFetchingHistory(true);
    getCaseChat(caseId)
      .then((data) => {
        setMessages(data.messages || []);
        setTimeout(scrollToBottom, 100);
      })
      .catch((err) => console.error("Errore caricamento chat:", err))
      .finally(() => {
        setFetchingHistory(false);
        setTimeout(() => inputRef.current?.focus(), 150);
      });
  }, [caseId, isOpen]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (textToSend) => {
    const text = (textToSend || input).trim();
    if (!text || loading || !caseId) return;

    // Aggiungi immediatamente il messaggio utente per reattività UI
    const tempUserMsg = {
      id: "temp-" + Date.now(),
      case_id: caseId,
      sender: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await sendCaseChatMessage(caseId, text);
      if (res && res.assistant_message) {
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== tempUserMsg.id),
          res.user_message,
          res.assistant_message,
        ]);
      }
    } catch (err) {
      console.error("Errore invio messaggio chat:", err);
      const errMsg = {
        id: "err-" + Date.now(),
        case_id: caseId,
        sender: "assistant",
        content: `⚠️ **Errore di comunicazione:** ${err.message || String(err)}. Verifica che LM Studio sia attivo sulla porta 1234 con il modello caricato.`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleClear = async () => {
    if (!confirm("Sei sicuro di voler cancellare la cronologia dei chiarimenti per questa pratica?")) return;
    try {
      await clearCaseChat(caseId);
      setMessages([]);
    } catch (err) {
      console.error("Errore cancellazione chat:", err);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const quickPrompts = [
    "Come hai ottenuto i dati identificativi (REA e Sede) nel Cap. 2.1?",
    "Come hai unificato i soci nella compagine sociale (Cap. 2.2)?",
    "Spiegami da quali documenti derivano i debiti del Cap. 5",
    "Come è stato calcolato il MOL nel bilancio 2025?",
  ];

  // Helper formattazione markdown leggera (grassetti, elenchi, citazioni)
  const renderFormattedText = (content) => {
    if (!content) return null;
    const lines = content.split("\n");
    return lines.map((line, idx) => {
      // Intestazioni ##
      if (line.startsWith("## ")) {
        return <h4 key={idx} style={{ margin: "10px 0 4px", fontSize: 14, fontWeight: 700, color: "var(--pd-primary)" }}>{line.replace("## ", "")}</h4>;
      }
      if (line.startsWith("### ")) {
        return <h5 key={idx} style={{ margin: "8px 0 4px", fontSize: 13, fontWeight: 700, color: "var(--pd-text)" }}>{line.replace("### ", "")}</h5>;
      }
      // Citazioni >
      if (line.startsWith("> ")) {
        return (
          <blockquote key={idx} style={{ margin: "6px 0", padding: "6px 12px", background: "rgba(37,99,235,0.06)", borderLeft: "3px solid var(--pd-accent)", borderRadius: 4, fontSize: 12.5, fontStyle: "italic" }}>
            {line.replace("> ", "")}
          </blockquote>
        );
      }
      // Elenco puntato
      if (line.trim().startsWith("- ") || line.trim().startsWith("• ")) {
        const itemText = line.trim().replace(/^[-•]\s*/, "");
        return (
          <div key={idx} style={{ display: "flex", gap: 6, margin: "3px 0 3px 6px", fontSize: 13, lineHeight: 1.5 }}>
            <span style={{ color: "var(--pd-accent)", fontWeight: 700 }}>•</span>
            <div>{renderInlineFormatting(itemText)}</div>
          </div>
        );
      }
      // Linea vuota
      if (!line.trim()) {
        return <div key={idx} style={{ height: 6 }} />;
      }
      // Paragrafo standard
      return (
        <p key={idx} style={{ margin: "0 0 4px", fontSize: 13, lineHeight: 1.55 }}>
          {renderInlineFormatting(line)}
        </p>
      );
    });
  };

  const renderInlineFormatting = (text) => {
    // Sostituzione semplice per **grassetto** e `codice/file`
    const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={i} style={{ background: "rgba(0,0,0,0.06)", padding: "1px 5px", borderRadius: 4, fontSize: 12, fontFamily: "monospace", color: "#b91c1c" }}>
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
  };

  if (!isOpen) return null;

  return (
    <div
      className="no-print"
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: "100%",
        maxWidth: 480,
        backgroundColor: "var(--pd-surface)",
        boxShadow: "-8px 0 25px rgba(0, 0, 0, 0.18)",
        zIndex: 9998,
        display: "flex",
        flexDirection: "column",
        borderLeft: "1px solid var(--pd-border)",
        animation: "slideInRight 0.2s ease-out",
      }}
    >
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>

      {/* HEADER */}
      <div
        style={{
          padding: "14px 18px",
          background: "var(--pd-primary)",
          color: "#ffffff",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid rgba(255,255,255,0.1)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: "50%",
              background: "var(--pd-accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20, color: "#fff" }}>
              smart_toy
            </span>
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14.5, display: "flex", alignItems: "center", gap: 6 }}>
              Assistente DossierLex AI
              <span
                style={{
                  background: "#16a34a",
                  color: "#fff",
                  fontSize: 10,
                  fontWeight: 700,
                  padding: "1px 6px",
                  borderRadius: 10,
                }}
              >
                Qwen 27B
              </span>
            </div>
            <div style={{ fontSize: 11.5, opacity: 0.85 }}>
              Fascicolo: {clientName || "Cliente"}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleClear}
              title="Pulisci cronologia chat"
              style={{
                background: "transparent",
                border: "none",
                color: "#ffffff",
                opacity: 0.8,
                cursor: "pointer",
                padding: 4,
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>restart_alt</span>
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            title="Chiudi pannello chat"
            style={{
              background: "transparent",
              border: "none",
              color: "#ffffff",
              cursor: "pointer",
              padding: 4,
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 22 }}>close</span>
          </button>
        </div>
      </div>

      {/* MESSAGES BODY */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 16,
          background: "var(--pd-surface-low, #fcfbfa)",
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        {fetchingHistory && (
          <div style={{ textAlign: "center", padding: 20, color: "var(--pd-text-muted)", fontSize: 13 }}>
            <span className="material-symbols-outlined" style={{ animation: "spin 1s linear infinite", fontSize: 20, verticalAlign: "middle", marginRight: 6 }}>
              sync
            </span>
            Caricamento chiarimenti sul fascicolo...
          </div>
        )}

        {messages.length === 0 && !fetchingHistory && (
          <div style={{ textAlign: "center", padding: "24px 12px" }}>
            <div
              style={{
                width: 44,
                height: 44,
                margin: "0 auto 12px",
                borderRadius: "50%",
                background: "rgba(37,99,235,0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--pd-accent)",
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 26 }}>psychology</span>
            </div>
            <h4 style={{ margin: "0 0 6px", fontSize: 15, fontWeight: 700, color: "var(--pd-primary)" }}>
              Chiedi chiarimenti sull&apos;analisi
            </h4>
            <p style={{ margin: "0 0 18px", fontSize: 12.5, color: "var(--pd-text-muted)", lineHeight: 1.5 }}>
              Interroga l&apos;AI su come sono stati ottenuti specifici numeri, da quali documenti derivano i debiti o perché determinati soci o voci sono stati riclassificati.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 8, textAlign: "left" }}>
              <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--pd-text-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                Domande suggerite:
              </div>
              {quickPrompts.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSend(q)}
                  disabled={loading}
                  style={{
                    background: "var(--pd-surface, #ffffff)",
                    border: "1px solid var(--pd-border)",
                    borderRadius: "var(--pd-radius)",
                    padding: "8px 12px",
                    fontSize: 12.5,
                    textAlign: "left",
                    color: "var(--pd-text)",
                    cursor: "pointer",
                    transition: "all 0.12s",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "var(--pd-accent)";
                    e.currentTarget.style.background = "#f8fafc";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--pd-border)";
                    e.currentTarget.style.background = "var(--pd-surface, #ffffff)";
                  }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 16, color: "var(--pd-accent)" }}>
                    help_outline
                  </span>
                  <span>{q}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => {
          const isUser = m.sender === "user";
          return (
            <div
              key={m.id}
              style={{
                alignSelf: isUser ? "flex-end" : "flex-start",
                maxWidth: "88%",
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              <div
                style={{
                  background: isUser ? "var(--pd-primary)" : "var(--pd-surface, #ffffff)",
                  color: isUser ? "#ffffff" : "var(--pd-text)",
                  border: isUser ? "none" : "1px solid var(--pd-border)",
                  borderRadius: isUser ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
                  padding: "10px 14px",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                }}
              >
                {isUser ? (
                  <div style={{ fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
                    {m.content}
                  </div>
                ) : (
                  <div>
                    {renderFormattedText(m.content)}

                    {/* AZIONE DI FEEDBACK PER IL REPORT */}
                    <div style={{ marginTop: 10, paddingTop: 8, borderTop: "1px solid var(--pd-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 10.5, color: "var(--pd-text-muted)" }}>
                        {m.context_meta?.model ? `Modello: ${m.context_meta.model.split("/").pop()}` : "DossierLex AI"}
                      </span>
                      {onApplyInstruction && (
                        <button
                          type="button"
                          onClick={() => {
                            // Estrai la prima citazione o suggerimento se presente
                            onApplyInstruction(m.content);
                          }}
                          title="Copia o usa questa spiegazione per inserire una regola nel Report"
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "var(--pd-accent)",
                            fontSize: 11.5,
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "2px 6px",
                            borderRadius: 4,
                          }}
                        >
                          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
                            rate_review
                          </span>
                          Usa per Revisione
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
              <span
                style={{
                  fontSize: 10,
                  color: "var(--pd-text-muted)",
                  alignSelf: isUser ? "flex-end" : "flex-start",
                  padding: "0 4px",
                }}
              >
                {m.created_at ? new Date(m.created_at).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" }) : ""}
              </span>
            </div>
          );
        })}

        {loading && (
          <div
            style={{
              alignSelf: "flex-start",
              maxWidth: "88%",
              background: "var(--pd-surface, #ffffff)",
              border: "1px solid var(--pd-border)",
              borderRadius: "14px 14px 14px 2px",
              padding: "10px 14px",
              display: "flex",
              alignItems: "center",
              gap: 8,
              color: "var(--pd-text-muted)",
              fontSize: 12.5,
            }}
          >
            <span className="material-symbols-outlined" style={{ animation: "spin 1s linear infinite", fontSize: 18, color: "var(--pd-accent)" }}>
              autorenew
            </span>
            <span>Qwen 27B sta esaminando i documenti del fascicolo...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* FOOTER INPUT */}
      <div
        style={{
          padding: 12,
          background: "var(--pd-surface, #ffffff)",
          borderTop: "1px solid var(--pd-border)",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <textarea
            ref={inputRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Chiedi: es. 'Come hai ottenuto questo dato per la tabella 5.1?'"
            disabled={loading}
            style={{
              flex: 1,
              background: "var(--pd-surface-low, #fcfbfa)",
              border: "1px solid var(--pd-border)",
              borderRadius: "var(--pd-radius)",
              padding: "8px 10px",
              fontSize: 13,
              color: "var(--pd-text)",
              outline: "none",
              resize: "none",
              boxSizing: "border-box",
              fontFamily: "inherit",
              lineHeight: 1.4,
            }}
          />
          <button
            type="button"
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            style={{
              background: input.trim() && !loading ? "var(--pd-accent)" : "var(--pd-surface-low)",
              color: input.trim() && !loading ? "#ffffff" : "var(--pd-text-muted)",
              border: "1px solid var(--pd-border)",
              borderRadius: "var(--pd-radius)",
              width: 38,
              height: 38,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: input.trim() && !loading ? "pointer" : "default",
              transition: "all 0.15s",
              flexShrink: 0,
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
              send
            </span>
          </button>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, color: "var(--pd-text-muted)" }}>
          <span>Invio per inviare, Shift+Invio per a capo</span>
          <span>Offline • 100% Locale</span>
        </div>
      </div>
    </div>
  );
}

