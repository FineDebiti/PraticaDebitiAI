import { Children } from "react";

export function Section({ title, children }) {
  return (
    <div style={{ background: "var(--pd-surface)", border: "1px solid var(--pd-border)", borderRadius: 8, padding: 18, marginBottom: 18 }}>
      <h2 style={{ color: "var(--pd-accent)", marginTop: 0, fontSize: 18 }}>{title}</h2>
      {children}
    </div>
  );
}

export function ToolsBar({ children }) {
  return (
    <div style={{ background: "var(--pd-surface-2)", border: "1px solid var(--pd-border-strong)", borderRadius: 8, padding: "12px 14px", marginBottom: 18 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--pd-primary)", textTransform: "uppercase", letterSpacing: 0.3, marginBottom: 10 }}>
        Strumenti per popolare questa sezione
      </div>
      <div className={"tools-grid " + (Children.count(children) === 2 ? "tools-2col" : "tools-auto")}>
        {children}
      </div>
    </div>
  );
}

export function Stat({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--pd-text-muted)", textTransform: "uppercase", letterSpacing: 0.3 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: "bold", color: "var(--pd-primary)" }}>{value}</div>
    </div>
  );
}

export function CrBadge({ on, okText, alertText, tone }) {
  const v = on ? (tone === "warning" ? "warn" : "danger") : "ok";
  return <span className={`pd-badge pd-badge--${v}`}>{on ? alertText : okText}</span>;
}
