/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy API calls to the orchestrator so the portal works without CORS config
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.ORCHESTRATOR_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
