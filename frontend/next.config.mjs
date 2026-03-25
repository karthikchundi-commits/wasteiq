/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api-proxy/:path*",
        destination: "https://wasteiq-rho.vercel.app/:path*",
      },
    ];
  },
};

export default nextConfig;
