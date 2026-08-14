def check_select(env):
    router = env['nexora.ai_cost_router']
    pm = env['nexora.ai_provider_manager']
    adapters = pm._get_adapters()
    task = 'code_generation'
    try:
        adapter = router.select_provider(task, adapters)
        print(f"Selected adapter for {task}:", adapter.get_provider_name())
    except Exception as e:
        print("Error:", e)

if "env" in locals():
    check_select(env)
