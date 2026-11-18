import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  output: "standalone", // self-contained server for the Docker image
  devIndicators: false, // the dev badge sat on top of the account menu in the sidebar
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
}

export default nextConfig
