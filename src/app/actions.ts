"use server";

import { createClient } from "@supabase/supabase-js";
import { parseHandles } from "@/lib/handleParser";
import { revalidatePath } from "next/cache";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

// Use service role for backend actions since we don't have a login UI yet
const supabase = createClient(supabaseUrl, supabaseKey);

export async function bulkImportCreators(
  rawText: string, 
  trackingType: string, 
  tags: string,
  assignedPlatforms?: Record<string, string>
) {
  try {
    // 1. Ensure we have a default workspace
    let { data: workspace } = await supabase
      .from('workspaces')
      .select('id')
      .order('created_at', { ascending: true })
      .limit(1)
      .single();

    if (!workspace) {
        throw new Error("No workspaces found. Please run the DB seed script.");
    }

    const wsId = workspace.id;
    const tagArray = tags ? tags.split(',').map(t => t.trim()).filter(Boolean) : [];

    // 2. Parse handles
    const parsed = parseHandles(rawText);
    const validHandles = parsed.filter(h => !h.isDuplicate);

    // 3. Insert each handle as a distinct creator in "processing" state
    // In reality, if it's one person with IG and TikTok, the discovery script will merge them later.
    // For V1 MVP, each parsed handle is queued separately.
    const promises = validHandles.map(async (ph, idx) => {
        const finalPlatform = assignedPlatforms?.[`${idx}`] || ph.platform;
        if (!finalPlatform && ph.needsPlatformHint) return null;

        const handleString = ph.handle;
        if (!handleString) return null;
        
        // Use a generated slug
        const slug = handleString.replace(/[^a-zA-Z0-9]/g, '').toLowerCase() + '-' + Date.now() + Math.floor(Math.random()*1000);

        // Create the Creator Record
        const { data: creator, error: cErr } = await supabase.from('creators').insert({
            workspace_id: wsId,
            canonical_name: handleString, // Placeholder until discovery
            slug: slug,
            primary_platform: finalPlatform !== 'unknown' ? finalPlatform : null,
            known_usernames: [handleString],
            tracking_type: trackingType,
            tags: tagArray,
            onboarding_status: 'processing'
        }).select('id').single();

        if (cErr || !creator) {
            console.error("Error inserting creator:", cErr);
            return null;
        }

        // We also want to kick off the background discovery log!
        await supabase.from('discovery_runs').insert({
            workspace_id: wsId,
            creator_id: creator.id,
            input_handle: handleString,
            input_platform_hint: finalPlatform !== 'unknown' ? finalPlatform : null,
            status: 'pending' // Python worker will pick this up
        });

        return creator.id;
    });

    await Promise.all(promises);

    // Refresh UI
    revalidatePath('/creators');
    return { success: true };
    
  } catch (error: any) {
    console.error("Bulk Import Error:", error);
    return { success: false, error: error.message };
  }
}

