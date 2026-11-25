/** Static export: FastAPI serves the built files, so the whole app is one deployable service. */
const dev = process.env.NODE_ENV === "development";
const nextConfig = {
  output: dev ? undefined : "export",
  trailingSlash: true,
  images: { unoptimized: true },
  // `npm run dev` runs on :3000 and proxies the API on :8000.
  ...(dev && { rewrites: async () => [{ source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }] }),
};
export default nextConfig;
