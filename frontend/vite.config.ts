import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "auto",
      devOptions: {
        enabled: true,
        type: "module",
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        navigateFallback: "/index.html",
        runtimeCaching: [
          {
            urlPattern: /^http:\/\/(localhost|127\.0\.0\.1):8000\/(departments|health)/,
            handler: "NetworkFirst",
            options: { cacheName: "civicfix-api-cache", networkTimeoutSeconds: 3 },
          },
          {
            urlPattern: /^http:\/\/(localhost|127\.0\.0\.1):8000\/uploads\//,
            handler: "CacheFirst",
            options: { cacheName: "civicfix-image-cache", expiration: { maxEntries: 100 } },
          },
        ],
      },
      manifest: {
        name: "CivicFix — Report Civic Issues",
        short_name: "CivicFix",
        description: "Report and track civic issues in your city, even offline.",
        theme_color: "#0f766e",
        background_color: "#ffffff",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
  },
});
