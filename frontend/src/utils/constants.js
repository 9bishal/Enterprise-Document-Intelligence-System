const configuredApiBase = import.meta.env.VITE_API_BASE;

if (import.meta.env.PROD && !configuredApiBase) {
  console.error(
    'VITE_API_BASE is not set. Set it to the deployed backend URL in Vercel, e.g. https://your-backend.onrender.com/api'
  );
}

export const API_BASE = configuredApiBase || 'http://localhost:8000/api';

export const PROVIDER_MODELS = {
  groq: [
    { id: "allam-2-7b", name: "Allam 2 7B (Free, 7K req/day, 500K tokens/day)" },
    { id: "qwen/qwen3.6-27b", name: "Qwen 3.6 27B (200K tokens/day)" },
    { id: "openai/gpt-oss-20b", name: "GPT-OSS 20B (200K tokens/day)" },
    { id: "openai/gpt-oss-120b", name: "GPT-OSS 120B (200K tokens/day)" },
    { id: "groq/compound", name: "Groq Compound (routes to other models)" },
    { id: "meta-llama/llama-prompt-guard-2-22m", name: "Llama Prompt Guard 22M" },
    { id: "meta-llama/llama-prompt-guard-2-86m", name: "Llama Prompt Guard 86M" }
  ],
  gemini: [
    { id: "gemini-1.5-flash", name: "Gemini 1.5 Flash (Default)" },
    { id: "gemini-1.5-pro", name: "Gemini 1.5 Pro (Analytical)" }
  ],
  openai: [
    { id: "gpt-4o-mini", name: "GPT-4o Mini (Cost-Effective)" },
    { id: "gpt-4o", name: "GPT-4o (High-Intelligence)" }
  ],
  ollama: [
    { id: "llama3", name: "Llama 3 (Local)" },
    { id: "mistral", name: "Mistral (Local)" },
    { id: "gemma2", name: "Gemma 2 (Local)" }
  ]
};

export function safeLocalStorage() {
  const store = {};
  return {
    getItem(key) {
      try {
        if (typeof localStorage !== 'undefined') {
          const v = localStorage.getItem(key);
          store[key] = v;
          return v;
        }
      } catch { /* localStorage unavailable (e.g. SSR) -> fall through to cache */ }
      return typeof store[key] !== 'undefined' ? store[key] : null;
    },
    setItem(key, value) {
      store[key] = value;
      try { localStorage.setItem(key, value); } catch { /* ignore */ }
    },
    removeItem(key) {
      delete store[key];
      try { localStorage.removeItem(key); } catch { /* ignore */ }
    }
  };
}
