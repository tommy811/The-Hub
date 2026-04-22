import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0";

// [supabase/functions/trigger-discovery/index.ts] — Triggers worker parsing
serve(async (req) => {
  try {
    const { run_id } = await req.json();
    if (!run_id) {
       return new Response(JSON.stringify({ error: "missing run_id" }), { status: 400 });
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Validate and claim
    const { data: run, error } = await supabase
      .from("discovery_runs")
      .update({ status: "processing" })
      .eq("id", run_id)
      .eq("status", "pending")
      .select()
      .single();

    if (error || !run) {
      return new Response(JSON.stringify({ error: "Run not found or not pending", details: error }), { status: 400 });
    }

    const workerUrl = Deno.env.get("WORKER_URL");
    if (workerUrl) {
       // Fire and forget
       fetch(workerUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ run_id })
       }).catch(e => console.error("Worker webhook failed:", e));
    }

    return new Response(JSON.stringify({ run_id, status: "triggered" }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), { status: 500 });
  }
});
