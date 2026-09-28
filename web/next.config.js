/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return { beforeFiles: [
      { source: '/', destination: '/api/view?p=friend' },
      { source: '/p/:k', destination: '/api/view?p=pult&k=:k' },
    ] };
  },
};
module.exports = nextConfig;
