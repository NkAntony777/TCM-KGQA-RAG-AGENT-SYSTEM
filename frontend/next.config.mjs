/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_BASE_URL || "http://localhost:8002"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
