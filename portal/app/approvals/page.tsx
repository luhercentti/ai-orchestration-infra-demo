"use client";
import { useEffect, useState } from "react";

const card: React.CSSProperties = {
  background: "#fff", borderRadius: 8, padding: 20,
  boxShadow: "0 1px 4px rgba(0,0,0,.1)", marginBottom: 16,
};
const badge = (color: string): React.CSSProperties => ({
  display: "inline-block", padding: "2px 10px", borderRadius: 12,
  background: color, color: "#fff", fontSize: 12, fontWeight: 600,
});
const btn = (color: string): React.CSSProperties => ({
  padding: "8px 20px", background: color, color: "#fff", border: "none",
  borderRadius: 6, cursor: "pointer", fontSize: 14, marginRight: 8,
});

function statusColor(run: any) {
  if (run.interrupts?.length) return "#e67e22";
  if (run.values?.status === "provisioned") return "#27ae60";
  if (run.values?.status === "rejected") return "#e74c3c";
  return "#95a5a6";
}

function statusLabel(run: any) {
  if (run.interrupts?.length) return "Pending approval";
  return run.values?.status ?? "running";
}

export default function Approvals() {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState<string | null>(null);
  const [approver, setApprover] = useState("platform-team");

  async function load() {
    setLoading(true);
    const res = await fetch("/api/requests");
    if (res.ok) setRuns(await res.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function decide(threadId: string, decision: "approved" | "rejected") {
    setApproving(threadId);
    await fetch(`/api/requests/${threadId}/approve`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ approval: decision, approver }),
    });
    await load();
    setApproving(null);
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Approval Queue</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            style={{ padding: "6px 10px", border: "1px solid #ccc", borderRadius: 6 }}
            placeholder="Your name"
            value={approver}
            onChange={e => setApprover(e.target.value)}
          />
          <button style={btn("#1a1a2e")} onClick={load}>Refresh</button>
        </div>
      </div>

      {loading && <p>Loading…</p>}
      {!loading && runs.length === 0 && <p style={{ color: "#777" }}>No requests yet.</p>}

      {runs.map(run => (
        <div key={run.thread_id} style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <strong>{run.raw_text}</strong>
              <div style={{ fontSize: 13, color: "#777", marginTop: 2 }}>
                by <strong>{run.requester}</strong> · thread: <code style={{ fontSize: 11 }}>{run.thread_id.slice(0, 8)}…</code>
              </div>
            </div>
            <span style={badge(statusColor(run))}>{statusLabel(run)}</span>
          </div>

          {run.values?.spec && (
            <table style={{ borderCollapse: "collapse", marginTop: 12, width: "100%", fontSize: 13 }}>
              <tbody>
                <tr><td style={{ padding: "3px 8px", fontWeight: 600, width: 160 }}>Resource</td><td>{run.values.spec.resource_type}</td></tr>
                <tr><td style={{ padding: "3px 8px", fontWeight: 600 }}>Team</td><td>{run.values.spec.team}</td></tr>
                <tr><td style={{ padding: "3px 8px", fontWeight: 600 }}>Environment</td><td>{run.values.spec.environment}</td></tr>
                <tr><td style={{ padding: "3px 8px", fontWeight: 600 }}>Name</td><td>{run.values.spec.name}</td></tr>
                {run.values.plan && (
                  <>
                    <tr><td style={{ padding: "3px 8px", fontWeight: 600 }}>Terraform module</td><td><code>{run.values.plan.module}</code></td></tr>
                    <tr><td style={{ padding: "3px 8px", fontWeight: 600 }}>Est. cost</td><td>${run.values.plan.estimated_monthly_cost_usd}/mo</td></tr>
                  </>
                )}
                {run.values.policy?.violations?.length > 0 && (
                  <tr><td style={{ padding: "3px 8px", fontWeight: 600, color: "red" }}>Violations</td>
                    <td style={{ color: "red" }}>{run.values.policy.violations.join(", ")}</td></tr>
                )}
              </tbody>
            </table>
          )}

          {run.interrupts?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <button style={btn("#27ae60")} disabled={approving === run.thread_id}
                onClick={() => decide(run.thread_id, "approved")}>
                {approving === run.thread_id ? "…" : "Approve"}
              </button>
              <button style={btn("#e74c3c")} disabled={approving === run.thread_id}
                onClick={() => decide(run.thread_id, "rejected")}>
                {approving === run.thread_id ? "…" : "Reject"}
              </button>
            </div>
          )}
        </div>
      ))}
    </>
  );
}
