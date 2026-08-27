/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// leaflet.heat has no published types; it's a side-effect import that
// attaches L.heatLayer(...) to the shared Leaflet namespace at runtime.
declare module "leaflet.heat";
