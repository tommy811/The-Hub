import { createClient } from '@supabase/supabase-js'
import * as dotenv from 'dotenv'
import path from 'path'

dotenv.config({ path: path.resolve(process.cwd(), '.env.local') })
dotenv.config({ path: path.resolve(process.cwd(), '.env') }) // fallback

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY

if (!supabaseUrl || !supabaseKey) {
  console.log("Missing Supabase credentials")
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

async function main() {
  // Find or create workspace
  let { data: ws } = await supabase.from('workspaces').select('id').eq('slug', 'default-workspace').single()
  
  if (!ws) {
    const { data: user } = await supabase.auth.admin.createUser({
      email: 'admin@agency.com',
      password: 'password123',
      email_confirm: true
    })
    const uid = user.user?.id || '00000000-0000-0000-0000-000000000001'
    
    // Create workspace
    const { data: newWs, error } = await supabase.from('workspaces').insert({
      name: 'Default Agency',
      slug: 'default-workspace',
      owner_id: uid
    }).select('id').single()
    
    if (error) {
       console.error("Error creating workspace:", error)
       return
    }
    ws = newWs
    
    // add member
    await supabase.from('workspace_members').insert({
      workspace_id: ws.id,
      user_id: uid,
      role: 'owner'
    })
  }

  console.log("WORKSPACE_ID=" + ws.id)
}

main()
