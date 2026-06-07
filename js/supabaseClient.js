import { APP_CONFIG } from "./config.js";

let supabase = null;

export function isSupabaseConfigured() {
  return Boolean(
    APP_CONFIG.supabaseUrl &&
    APP_CONFIG.supabaseAnonKey &&
    !APP_CONFIG.demoMode &&
    !APP_CONFIG.supabaseUrl.includes("REPLACE_WITH") &&
    !APP_CONFIG.supabaseAnonKey.includes("REPLACE_WITH")
  );
}

export async function getSupabaseClient() {
  if (!isSupabaseConfigured()) return null;
  if (supabase) return supabase;
  const mod = await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm");
  supabase = mod.createClient(APP_CONFIG.supabaseUrl, APP_CONFIG.supabaseAnonKey);
  return supabase;
}
