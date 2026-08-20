import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Infra Request Copilot",
  description: "Self-service infrastructure request portal",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, background: "#f5f5f5" }}>
        <nav style={{ background: "#1a1a2e", color: "#fff", padding: "12px 24px", display: "flex", gap: 24 }}>
          <strong>Infra Request Copilot</strong>
          <a href="/" style={{ color: "#a0c4ff", textDecoration: "none" }}>New Request</a>
          <a href="/approvals" style={{ color: "#a0c4ff", textDecoration: "none" }}>Approval Queue</a>
        </nav>
        <main style={{ maxWidth: 800, margin: "32px auto", padding: "0 16px" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
