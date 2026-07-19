import { createClient } from "@supabase/supabase-js";

/**
 * Server-only Supabase client using the service role key.
 * Never import this from a "use client" component — the service role
 * key must stay on the server.
 */
export function getSupabaseAdmin() {
  const url = process.env.SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceKey) {
    throw new Error(
      "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables"
    );
  }

  return createClient(url, serviceKey, {
    auth: { persistSession: false },
  });
}

export type Subscriber = {
  id: string;
  endpoint: string;
  p256dh: string;
  auth: string;
  created_at: string;
};

export type Listing = {
  id: string;
  url: string;
  company: string;
  created_at: string;
};
