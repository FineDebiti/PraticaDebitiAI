import { Children } from "react";

export function Section({ title, subtitle, badge, badgeTone = "info", icon, children, actions }) {
  return (
    <div
      className="pd-card"
      style={{
        background: "var(--pd-surface)",
        border: "1px solid var(--pd-border)",
        borderRadius: 8,
        padding: "20px 22px",
        marginBottom: 18,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 12,
          marginBottom: 14,
          paddingBottom: 10,
          borderBottom: "1px solid var(--pd-border-soft)",
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {icon && (
              <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 20, color: "var(--pd-accent)" }}>
                {icon}
              </span>
            )}
            <h2 style={{ fontSize: 17, margin: 0, color: "var(--pd-primary)", fontWeight: 700 }}>{title}</h2>
            {badge && (
              <span className={`pd-badge pd-badge--${badgeTone}`} style={{ fontSize: 11 }}>
                {badge}
              </span>
            )}
          </div>
          {subtitle && (
            <p style={{ margin: "4px 0 0", fontSize: 12.5, color: "var(--pd-text-muted)" }}>{subtitle}</p>
          )}
        </div>
        {actions && <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>{actions}</div>}
      </div>
      {children}
    </div>
  );
}

export function ToolsBar({ title = "Acquisizione Fonti e Strumenti Operativi", subtitle, children }) {
  return (
    <div
      className="pd-card"
      style={{
        background: "var(--pd-surface-low)",
        border: "1px solid var(--pd-border)",
        borderRadius: 8,
        padding: "16px 18px",
        marginBottom: 18,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 18, color: "var(--pd-accent)" }}>
            cloud_upload
          </span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 800,
              color: "var(--pd-primary)",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            {title}
          </span>
        </div>
        <span className="pd-badge pd-badge--info" style={{ fontSize: 11 }}>
          [D] Estrazione Automatica + SHA-256
        </span>
      </div>
      {subtitle && <p style={{ margin: "0 0 12px", fontSize: 12.5, color: "var(--pd-text-muted)" }}>{subtitle}</p>}
      <div className={"tools-grid " + (Children.count(children) === 2 ? "tools-2col" : "tools-auto")}>
        {children}
      </div>
    </div>
  );
}

export function Stat({ label, value, sub, badge, badgeTone = "neutral" }) {
  const isNull = value === null || value === undefined || value === "n.s." || value === "—";
  return (
    <div
      style={{
        background: "var(--pd-surface-low)",
        border: "1px solid var(--pd-border-soft)",
        borderRadius: 6,
        padding: "10px 12px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
        <div style={{ fontSize: 11, color: "var(--pd-text-muted)", textTransform: "uppercase", letterSpacing: 0.3, fontWeight: 700 }}>
          {label}
        </div>
        {badge && (
          <span className={`pd-badge pd-badge--${badgeTone}`} style={{ fontSize: 10, padding: "1px 6px" }}>
            {badge}
          </span>
        )}
      </div>
      <div
        style={{
          fontSize: isNull ? 13 : 16,
          fontWeight: 700,
          color: isNull ? "var(--pd-text-muted)" : "var(--pd-primary)",
          marginTop: 4,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value === "n.s." ? "Non rilevato (NULL)" : value}
      </div>
      {sub && <div style={{ fontSize: 11, color: "var(--pd-text-muted)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export function CrBadge({ on, okText, alertText, tone }) {
  const v = on ? (tone === "warning" ? "warn" : "danger") : "ok";
  return <span className={`pd-badge pd-badge--${v}`}>{on ? alertText : okText}</span>;
}
