"use client";
import { useState } from "react";

const card: React.CSSProperties = {
  background: "#fff", borderRadius: 8, padding: 24, boxShadow: "0 1px 4px rgba(0,0,0,.1)",
};
const label: React.CSSProperties = { display: "block", fontWeight: 600, marginBottom: 6 };
const input: React.CSSProperties = {
  width: "100%", padding: "10px 12px", border: "1px solid #ccc", borderRadius: 6,
  fontSize: 14, boxSizing: "border-box",
};
const btn: React.CSSProperties = {
  marginTop: 16, padding: "10px 24px", background: "#1a1a2e", color: "#fff",
  border: "none", borderRadius: 6, cursor: "pointer", fontSize: 15,
};
const badge = (color: string): React.CSSProperties => ({
  display: "inline-block", padding: "2px 10px", borderRadius: 12,
  background: color, color: "#fff", fontSize: 12, fontWeight: 600,
});

export default function NewRequest() {
  const [rawText, setRawText] = useState("");
  const [requester, setRequester] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch("/api/requests", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ raw_text: rawText, requester }),
      });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h1 style={{ marginBottom: 24 }}>New Infrastructure Request</h1>
      <div style={card}>
        <p style={{ marginTop: 0, color: "#555" }}>
          Describe what you need in plain language. The AI agents will parse it,
          check policy, generate a Terraform plan, and pause for platform-team approval.
        </p>
        <form onSubmit={submit}>
          <div style={{ marginBottom: 16 }}>
            <label style={label}>Request</label>
            <textarea
              style={{ ...input, height: 80, resize: "vertical" }}
              placeholder='e.g. "I need a Postgres database for team billing, staging"'
              value={rawText}
              onChange={e => setRawText(e.target.value)}
              required
            />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={label}>Your name / team</label>
            <input style={input} placeholder="e.g. alice" value={requester}
              onChange={e => setRequester(e.target.value)} required />
          </div>
          <button style={btn} disabled={loading}>{loading ? "Submitting…" : "Submit request"}</button>
        </form>
      </div>

      {error && <div style={{ marginTop: 16, color: "red" }}>{error}</div>}

      {result && (
        <div style={{ ...card, marginTop: 24 }}>
          <h2 style={{ marginTop: 0 }}>Request submitted ✓</h2>
          <p><strong>Thread ID:</strong> <code>{result.thread_id}</code></p>
          <p>
            <strong>Status:</strong>{" "}
            <span style={badge(result.interrupts?.length ? "#e67e22" : "#27ae60")}>
              {result.interrupts?.length ? "Waiting for approval" : result.values?.status ?? "running"}
            </span>
          </p>
          {result.values?.spec && (
            <table style={{ borderCollapse: "collapse", width: "100%", marginTop: 12 }}>
              <tbody>
                {Object.entries(result.values.spec).map(([k, v]) => (
                  <tr key={k} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={{ padding: "6px 8px", fontWeight: 600, width: 160 }}>{k}</td>
                    <td style={{ padding: "6px 8px" }}>{String(v)}</td>
                  </tr>
                ))}
                <tr style={{ borderBottom: "1px solid #eee" }}>
                  <td style={{ padding: "6px 8px", fontWeight: 600 }}>Est. monthly cost</td>
                  <td style={{ padding: "6px 8px" }}>${result.values.plan?.estimated_monthly_cost_usd}/mo</td>
                </tr>
              </tbody>
            </table>
          )}
          <p style={{ marginBottom: 0, color: "#555", fontSize: 13 }}>
            A platform engineer will review and approve this in the{" "}
            <a href="/approvals">Approval Queue</a>.
          </p>
        </div>
      )}
    </>
  );
}
