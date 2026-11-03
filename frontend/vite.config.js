import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate", // versão nova do app entra sozinha
      includeAssets: ["icon.svg"],
      manifest: {
        name: "Rewind",
        short_name: "Rewind",
        description: "Uma selfie por dia até o grande dia.",
        lang: "pt-BR",
        start_url: "/",
        display: "standalone",
        background_color: "#0f1115",
        theme_color: "#0f1115",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // O service worker guarda só o app (HTML/JS/CSS). Nada de /api: fotos e dados
        // pessoais nunca ficam no cache do navegador.
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],
  server: {
    // Em desenvolvimento, o Vite repassa /api pro FastAPI. Assim front e API
    // ficam na mesma origem e o cookie funciona igual à produção.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
