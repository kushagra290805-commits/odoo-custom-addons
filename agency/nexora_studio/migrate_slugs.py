import re
def _generate_slug(name):
    if not name:
        return "unnamed-workspace"
    slug = name.lower()
    slug = slug.replace(' ', '-')
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    if not slug:
        slug = "workspace"
    return slug

def _get_unique_slug(env, base_slug, current_id=None):
    slug = base_slug
    counter = 2
    domain = [('workspace_slug', '=', slug)]
    if current_id:
        domain.append(('id', '!=', current_id))
        
    while env['nexora.workspace'].search_count(domain) > 0:
        slug = f"{base_slug}-{counter}"
        counter += 1
        domain = [('workspace_slug', '=', slug)]
        if current_id:
            domain.append(('id', '!=', current_id))
    return slug

# Only run if nexora.workspace table exists in DB, we bypass ORM schema checks via SQL for initial population
env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='nexora_workspace' and column_name='workspace_slug'")
if not env.cr.fetchone():
    env.cr.execute("ALTER TABLE nexora_workspace ADD COLUMN IF NOT EXISTS workspace_slug VARCHAR")

env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='nexora_workspace' and column_name='initialized_at'")
if not env.cr.fetchone():
    env.cr.execute("ALTER TABLE nexora_workspace ADD COLUMN IF NOT EXISTS initialized_at TIMESTAMP")

workspaces = env['nexora.workspace'].search([])
for ws in workspaces:
    # Use direct SQL if ORM hasn't loaded the field yet, or ORM if it has. We use SQL to be safe before upgrade.
    base = _generate_slug(ws.name)
    slug = _get_unique_slug(env, base, ws.id)
    print(f"Setting slug {slug} for {ws.name} (ID: {ws.id})")
    env.cr.execute("UPDATE nexora_workspace SET workspace_slug=%s WHERE id=%s", (slug, ws.id))
    
    # Also initialize_at
    if ws.status == 'ready' or ws.workspace_path:
        env.cr.execute("UPDATE nexora_workspace SET initialized_at=create_date WHERE id=%s", (ws.id,))

env.cr.commit()
print("Migration complete.")
