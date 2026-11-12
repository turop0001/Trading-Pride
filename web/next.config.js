/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return { beforeFiles: [
      { source: '/', destination: '/api/view?p=friend' },
      { source: '/p/:k', destination: '/api/view?p=pult&k=:k' },
      { source: '/l/:k', destination: '/api/view?p=ladder&k=:k' },
    ] };
  },
};
module.exports = nextConfig;
