const configuredApiRoot = import.meta.env.VITE_API_ROOT;

if (!configuredApiRoot) {
  throw new Error("VITE_API_ROOT is niet ingesteld.");
}

export const API_ROOT = configuredApiRoot.replace(/\/+$/, "");