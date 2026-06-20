import { useState, useEffect, useRef } from "react";

// ── Tiny icon components ───────────────────────────────────────────────────────
const Icon = ({ d, s = 20 }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);
const SunIco = () => <Icon s={15} d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0z" />;
const MoonIco = () => <Icon s={15} d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />;
const GlobeIco = () => <Icon d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2z" />;
const SearchIco = () => <Icon s={16} d="M11 17.25a6.25 6.25 0 1 0 0-12.5 6.25 6.25 0 0 0 0 12.5zM16 16l4.5 4.5" />;
const TrashIco = () => <Icon s={16} d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />;
const DownloadIco = () => <Icon s={16} d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />;
const RefreshIco = () => <Icon s={16} d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />;
const HelpIco = () => <Icon s={15} d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01" />;
const CheckIco = () => <Icon s={13} d="M20 6 9 17 4 12" />;

// ── Theme toggle ───────────────────────────────────────────────────────────────
function Toggle({ dark, onToggle }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ color: dark ? "#3a4a70" : "#f5a623", transition: "color .3s" }}><SunIco /></span>
      <button
        onClick={onToggle}
        aria-label="Toggle theme"
        style={{
          width: 40, height: 22, borderRadius: 99, border: "none", cursor: "pointer", position: "relative",
          background: dark ? "linear-gradient(135deg,#4f6ef7,#7c5cfc)" : "linear-gradient(135deg,#94a3b8,#cbd5e1)",
          transition: "background .4s",
        }}
      >
        <span style={{
          position: "absolute", top: 3, left: 3, width: 16, height: 16, borderRadius: "50%", background: "#fff",
          boxShadow: "0 1px 4px rgba(0,0,0,.3)", transition: "transform .35s cubic-bezier(.34,1.56,.64,1)",
          transform: dark ? "translateX(18px)" : "translateX(0)",
        }} />
      </button>
      <span style={{ color: dark ? "#7c5cfc" : "#94a3b8", transition: "color .3s" }}><MoonIco /></span>
    </div>
  );
}

// ── Score card ─────────────────────────────────────────────────────────────────
function ScoreCard({ label, value, color, grade, dark }) {
  const c = { blue: "#4f6ef7", amber: "#f5a623", green: "#10e89a", purple: "#a78bfa" }[color];
  const bg = dark ? "rgba(0,0,0,.3)" : "rgba(255,255,255,.7)";
  const border = dark ? "rgba(255,255,255,.07)" : "rgba(0,0,0,.08)";
  return (
    <div style={{ flex: 1, minWidth: 0, background: bg, border: `1px solid ${border}`, borderRadius: 14, padding: "1rem", display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: dark ? "#7a88b8" : "#64748b" }}>{label}</span>
      <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
        <span style={{ fontSize: 28, fontWeight: 900, letterSpacing: "-.04em", color: value !== null ? c : (dark ? "#2a3560" : "#e2e8f0") }}>
          {value !== null ? value : "––"}
        </span>
        <span style={{ fontSize: 13, color: dark ? "#3a4a70" : "#cbd5e1" }}>/100</span>
      </div>
      <span style={{ fontSize: 10, fontWeight: 700, color: value !== null ? c : (dark ? "#1e2a4a" : "#f0f4ff") }}>{value !== null ? grade : "–"}</span>
    </div>
  );
}

// ── How It Works step ──────────────────────────────────────────────────────────
function HowStep({ n, icon, label, dark }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 8, textAlign: "center" }}>
      <div style={{ width: 52, height: 52, borderRadius: 14, background: "rgba(79,110,247,.1)", border: "1px solid rgba(79,110,247,.2)", display: "flex", alignItems: "center", justifyContent: "center", position: "relative", color: "#7a9bff", fontSize: 22 }}>
        {icon}
        <span style={{ position: "absolute", bottom: -6, right: -6, width: 18, height: 18, borderRadius: "50%", background: "linear-gradient(135deg,#4f6ef7,#7c5cfc)", fontSize: 9, fontWeight: 800, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center" }}>{n}</span>
      </div>
      <span style={{ fontSize: 11, fontWeight: 600, color: dark ? "#7a88b8" : "#475569", lineHeight: 1.3 }}>{label}</span>
    </div>
  );
}

// ── Progress step ──────────────────────────────────────────────────────────────
function ProgStep({ label, status }) {
  const colors = { done: "#10e89a", active: "#7a9bff", wait: "#3a4a70" };
  const dotBg = { done: "#10e89a", active: "#4f6ef7", wait: "rgba(255,255,255,.08)" };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 500 }}>
      <span style={{ width: 20, height: 20, borderRadius: "50%", background: dotBg[status], display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, animation: status === "active" ? "aeo-pulse 1s ease-in-out infinite" : "none" }}>
        {status === "done" ? <CheckIco /> : status === "active" ? <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#fff", animation: "aeo-spin 1s linear infinite", display: "block" }} /> : <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#3a4a70", display: "block" }} />}
      </span>
      <span style={{ color: colors[status] }}>{label}</span>
    </div>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────────
const STEPS = ["Fetching website", "Content analysis", "Technical analysis", "Brand analysis", "Generating report"];

export default function AEOAudit() {
  const [dark, setDark] = useState(() => {
    try { const s = localStorage.getItem("aeo-dark"); if (s) return s === "1"; } catch {}
    return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState("idle"); // idle | loading | done
  const [step, setStep] = useState(-1);
  const [report, setReport] = useState(null);
  const [counts, setCounts] = useState([null, null, null, null]);
  const timer = useRef(null);

  useEffect(() => { try { localStorage.setItem("aeo-dark", dark ? "1" : "0"); } catch {} }, [dark]);

 async function start() {
  if (!url.trim()) return;

  try {
    setPhase("loading");

    const response = await fetch(
  "https://aeo-report-generator-3.onrender.com/generate-pdf-report",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      website: url,
    }),
  }
);

    if (!response.ok) {
      throw new Error("Failed to generate report");
    }

    // PDF download
    const blob = await response.blob();

    const fileURL = window.URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = fileURL;
    link.download = "AEO_Report.pdf";

    document.body.appendChild(link);
    link.click();

    link.remove();

    setPhase("done");

  } catch (error) {
    console.error(error);
    alert("Report generation failed");
    setPhase("idle");
  }
}

  function reset() {
    clearInterval(timer.current);
    setUrl(""); setPhase("idle"); setStep(-1); setReport(null); setCounts([null,null,null,null]);
  }

  const bg = dark ? "linear-gradient(160deg,#08091a 0%,#0d1030 50%,#08091a 100%)" : "linear-gradient(160deg,#eef2ff 0%,#f0f7ff 50%,#e8f4fd 100%)";
  const cardBg = dark ? "rgba(255,255,255,.04)" : "rgba(255,255,255,.85)";
  const cardBorder = dark ? "rgba(255,255,255,.09)" : "rgba(0,0,0,.08)";
  const text = dark ? "#f0f4ff" : "#0f172a";
  const muted = dark ? "#7a88b8" : "#475569";
  const inputBg = dark ? "rgba(0,0,0,.3)" : "rgba(255,255,255,.9)";
  const inputBorder = dark ? "rgba(255,255,255,.1)" : "rgba(0,0,0,.12)";

  return (
    <div style={{ minHeight: "100vh", background: bg, fontFamily: "'Inter','Segoe UI',system-ui,sans-serif", transition: "background .5s" }}>
      <style>{`@keyframes aeo-spin{to{transform:rotate(360deg)}} @keyframes aeo-pulse{0%,100%{box-shadow:0 0 0 0 rgba(79,110,247,.5)}50%{box-shadow:0 0 0 6px rgba(79,110,247,0)}} *{box-sizing:border-box;margin:0;padding:0} input::placeholder{color:${dark?"#3a4a70":"#94a3b8"}}`}</style>

      {/* Navbar */}
      <nav style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "1rem 1.5rem", position: "sticky", top: 0, zIndex: 50, background: dark ? "rgba(8,9,26,.85)" : "rgba(255,255,255,.85)", backdropFilter: "blur(20px)", borderBottom: `1px solid ${cardBorder}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 900, fontSize: 15, letterSpacing: "-.02em", color: text }}>
          <div style={{ display: "flex", gap: 3, alignItems: "flex-end" }}>
            {[9, 15, 12].map((h, i) => <span key={i} style={{ display: "block", width: 4, height: h, borderRadius: 2, background: "linear-gradient(180deg,#4f6ef7,#7c5cfc)" }} />)}
          </div>
          AEO Audit
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Toggle dark={dark} onToggle={() => setDark(d => !d)} />
          <button style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: muted, background: "rgba(255,255,255,.05)", border: `1px solid ${cardBorder}`, borderRadius: 8, padding: "6px 12px", cursor: "pointer", fontFamily: "inherit" }}>
            <HelpIco /> How it works
          </button>
        </div>
      </nav>

      <main style={{ maxWidth: 780, margin: "0 auto", padding: "0 1rem 4rem" }}>
        {/* Hero */}
        <div style={{ textAlign: "center", padding: "2.5rem 0 2rem" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", background: "rgba(79,110,247,.12)", color: "#7a9bff", border: "1px solid rgba(79,110,247,.25)", borderRadius: 99, padding: "5px 14px", marginBottom: "1.5rem" }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#4f6ef7", display: "inline-block" }} />
            AI Search Optimization
          </div>
          <h1 style={{ fontSize: "clamp(2rem,5vw,3.2rem)", fontWeight: 900, lineHeight: 1.1, letterSpacing: "-.035em", color: text, marginBottom: "1rem" }}>
            Analyze Your Website's<br />
            <span style={{ background: "linear-gradient(135deg,#4f6ef7 0%,#7c5cfc 40%,#c084fc 80%,#f472b6 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
              AI Search Readiness
            </span>
          </h1>
          <p style={{ color: muted, fontSize: 15, maxWidth: 480, margin: "0 auto", lineHeight: 1.7 }}>
            Get a complete AEO audit covering Content, Technical SEO, Brand Authority, and AI Search Readiness.
          </p>
        </div>

        {/* Input card */}
        <div style={{ background: cardBg, border: `1px solid ${cardBorder}`, borderRadius: 24, padding: "1.75rem", marginBottom: "1rem", backdropFilter: "blur(12px)" }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase", color: muted, marginBottom: ".75rem" }}>Enter website URL</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, background: inputBg, border: `1.5px solid ${inputBorder}`, borderRadius: 14, padding: "0 14px", marginBottom: "1rem", transition: "border-color .2s" }}
            onFocus={e => e.currentTarget.style.borderColor = "#4f6ef7"}
            onBlur={e => e.currentTarget.style.borderColor = inputBorder}
          >
            <span style={{ color: muted }}><GlobeIco /></span>
            <input
              value={url} onChange={e => setUrl(e.target.value)} onKeyDown={e => e.key === "Enter" && start()}
              type="url" placeholder="https://example.com" aria-label="Website URL"
              style={{ flex: 1, background: "none", border: "none", outline: "none", color: text, fontSize: 15, padding: "14px 0", fontFamily: "inherit" }}
            />
          </div>

          {phase === "loading" && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, padding: "1rem", background: "rgba(79,110,247,.06)", border: "1px solid rgba(79,110,247,.15)", borderRadius: 12, marginBottom: "1rem" }}>
              {STEPS.map((s, i) => <ProgStep key={s} label={s} status={i < step ? "done" : i === step ? "active" : "wait"} />)}
            </div>
          )}

          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={start} disabled={!url.trim() || phase === "loading"}
              style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, background: (!url.trim() || phase === "loading") ? "rgba(79,110,247,.4)" : "linear-gradient(135deg,#4f6ef7,#7c5cfc)", border: "none", borderRadius: 12, color: "#fff", fontWeight: 700, fontSize: 14, padding: 14, cursor: !url.trim() || phase === "loading" ? "not-allowed" : "pointer", fontFamily: "inherit", boxShadow: url.trim() && phase !== "loading" ? "0 4px 24px rgba(79,110,247,.35)" : "none", transition: "all .25s" }}
            >
              <SearchIco /> {phase === "loading" ? "Analyzing…" : "Generate Report"}
            </button>
            <button
              onClick={reset}
              style={{ display: "flex", alignItems: "center", gap: 7, background: dark ? "rgba(255,255,255,.05)" : "rgba(0,0,0,.04)", border: `1px solid ${cardBorder}`, borderRadius: 12, color: muted, fontWeight: 600, fontSize: 14, padding: "14px 20px", cursor: "pointer", fontFamily: "inherit", transition: "all .2s" }}
              onMouseEnter={e => { e.currentTarget.style.color = "#f87171"; e.currentTarget.style.borderColor = "rgba(248,113,113,.4)"; }}
              onMouseLeave={e => { e.currentTarget.style.color = muted; e.currentTarget.style.borderColor = cardBorder; }}
            >
              <TrashIco /> Clear
            </button>
          </div>
        </div>

        {/* How it works */}
        <div style={{ background: cardBg, border: `1px solid ${cardBorder}`, borderRadius: 24, padding: "1.75rem", marginBottom: "1rem", backdropFilter: "blur(12px)" }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase", color: muted, marginBottom: "1.25rem", textAlign: "center" }}>How it works</div>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 0 }}>
            {[
              { n: 1, label: "Enter URL", icon: <GlobeIco /> },
              null,
              { n: 2, label: "Analyze Content", icon: "📄" },
              null,
              { n: 3, label: "Technical", icon: "⚙️" },
              null,
              { n: 4, label: "Brand Authority", icon: "🛡️" },
              null,
              { n: 5, label: "Get Report", icon: "📊" },
            ].map((item, i) =>
              item
                ? <HowStep key={i} n={item.n} icon={item.icon} label={item.label} dark={dark} />
                : <div key={i} style={{ color: dark ? "#2a3560" : "#cbd5e1", fontSize: 16, marginTop: 24, padding: "0 2px", flexShrink: 0 }}>→</div>
            )}
          </div>
        </div>

        {/* Report */}
        <div style={{ background: cardBg, border: `1px solid ${cardBorder}`, borderRadius: 24, padding: "1.75rem", backdropFilter: "blur(12px)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: "1.25rem" }}>
            <div style={{ width: 60, height: 50, flexShrink: 0, opacity: .35 }}>
              <svg viewBox="0 0 60 50" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ width: "100%", height: "100%" }}>
                <rect x="2" y="2" width="56" height="46" rx="6" stroke="#4f6ef7" strokeWidth="1.5"/>
                <rect x="8" y="8" width="20" height="3" rx="1.5" fill="#4f6ef7" opacity=".5"/>
                <rect x="8" y="14" width="44" height="2" rx="1" fill="#2a3560"/>
                <rect x="8" y="19" width="36" height="2" rx="1" fill="#2a3560"/>
                <rect x="8" y="29" width="12" height="14" rx="2" fill="#4f6ef7" opacity=".3"/>
                <rect x="24" y="23" width="12" height="20" rx="2" fill="#7c5cfc" opacity=".4"/>
                <rect x="40" y="32" width="12" height="11" rx="2" fill="#c084fc" opacity=".3"/>
              </svg>
            </div>
            <div>
              {phase === "done"
                ? <><div style={{ fontWeight: 700, fontSize: 14, color: "#10e89a", marginBottom: 2 }}>✓ Report complete</div><div style={{ fontSize: 12, color: muted }}>{url}</div></>
                : <><div style={{ fontWeight: 700, fontSize: 14, color: text, marginBottom: 2 }}>No report generated yet.</div><div style={{ fontSize: 12, color: muted }}>Enter a website URL and click "Generate Report".</div></>}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: "1.25rem" }}>
            <ScoreCard label="Overall" value={counts[0]} color="blue" grade="Good" dark={dark} />
            <ScoreCard label="Content" value={counts[1]} color="amber" grade="Very Good" dark={dark} />
            <ScoreCard label="Technical" value={counts[2]} color="green" grade="Good" dark={dark} />
            <ScoreCard label="Brand" value={counts[3]} color="purple" grade="Fair" dark={dark} />
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            {[
              { label: "Download PDF Report", icon: <DownloadIco />, hc: "#4f6ef7", hb: "rgba(79,110,247,.4)", disabled: !report },
              { label: "Analyze Another Website", icon: <RefreshIco />, hc: "#a78bfa", hb: "rgba(167,139,250,.4)", disabled: false, action: reset },
            ].map(({ label, icon, hc, hb, disabled, action }) => (
              <button key={label} disabled={disabled} onClick={action}
                style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 7, background: "transparent", border: `1px solid ${cardBorder}`, borderRadius: 12, color: disabled ? (dark ? "#2a3560" : "#e2e8f0") : muted, fontWeight: 600, fontSize: 13, padding: 12, cursor: disabled ? "not-allowed" : "pointer", fontFamily: "inherit", transition: "all .2s" }}
                onMouseEnter={e => { if (!disabled) { e.currentTarget.style.color = hc; e.currentTarget.style.borderColor = hb; } }}
                onMouseLeave={e => { e.currentTarget.style.color = disabled ? (dark ? "#2a3560" : "#e2e8f0") : muted; e.currentTarget.style.borderColor = cardBorder; }}
              >
                {icon} {label}
              </button>
            ))}
          </div>
        </div>
      </main>

      <footer style={{ textAlign: "center", padding: "1.25rem", fontSize: 12, color: dark ? "#2a3560" : "#94a3b8", borderTop: `1px solid ${cardBorder}` }}>
        © 2025 AEO Audit Report Generator · AI Search Optimization for the Future
      </footer>
    </div>
  );
}