/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Главная страница — полный Пульт (тот же вид, что был в артефакте Claude), лежит в public/pult.html.
  async rewrites() {
    return { beforeFiles: [
      { source: '/', destination: '/pult.html' },
      { source: '/friend', destination: '/pult.html' },
    ] };
  },
};
module.exports = nextConfig;
