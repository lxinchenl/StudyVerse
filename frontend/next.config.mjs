/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@neo4j-nvl/base", "@neo4j-nvl/react"],
  optimizePackageImports: ["lucide-react"],
};

export default nextConfig;

