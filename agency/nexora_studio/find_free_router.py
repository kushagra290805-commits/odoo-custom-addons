def find_free_router(env):
    models = env['nexora.ai_model_catalog'].search([
        ('provider', '=', 'openrouter'),
        ('name', 'ilike', 'router')
    ])
    print(f"Found {len(models)} models matching 'router':")
    for m in models:
        print(f" - {m.model_id}: {m.name}")
        
    models2 = env['nexora.ai_model_catalog'].search([
        ('provider', '=', 'openrouter'),
        ('name', 'ilike', 'auto')
    ])
    print(f"Found {len(models2)} models matching 'auto':")
    for m in models2:
        print(f" - {m.model_id}: {m.name}")

if "env" in locals():
    find_free_router(env)
