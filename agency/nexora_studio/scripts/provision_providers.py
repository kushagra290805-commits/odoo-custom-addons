def provision_providers(env):
    Registry = env['nexora.provider.registry']
    
    providers_data = [
        {
            'provider_id': 'nvidia',
            'name': 'NVIDIA NIM',
            'category': 'ai',
            'provider_type': 'cloud',
            'compatibility_profile': 'nvidia_nim',
            'lifecycle_state': 'CONFIGURED',
            'is_active': True,
            'base_url': 'https://integrate.api.nvidia.com/v1',
            'priority_weight': 10,
            'supports_streaming': True,
            'supports_json': True,
            'supports_vision': True,
            'supports_tool_calling': True
        },
        {
            'provider_id': 'openrouter',
            'name': 'OpenRouter',
            'category': 'ai',
            'provider_type': 'cloud',
            'compatibility_profile': 'openai_compatible',
            'lifecycle_state': 'CONFIGURED',
            'is_active': True,
            'base_url': 'https://openrouter.ai/api/v1',
            'priority_weight': 20,
            'supports_streaming': True,
            'supports_json': True,
            'supports_vision': True,
            'supports_tool_calling': True
        },
        {
            'provider_id': 'airouter',
            'name': 'AIRouter.in',
            'category': 'ai',
            'provider_type': 'cloud',
            'compatibility_profile': 'openai_compatible',
            'lifecycle_state': 'CONFIGURED',
            'is_active': True,
            'base_url': 'https://api.airouter.in/v1',
            'priority_weight': 30,
            'supports_streaming': True,
            'supports_json': True,
            'supports_vision': True,
            'supports_tool_calling': True
        },
        {
            'provider_id': 'groq',
            'name': 'Groq',
            'category': 'ai',
            'provider_type': 'cloud',
            'compatibility_profile': 'openai_compatible',
            'lifecycle_state': 'CONFIGURED',
            'is_active': True,
            'base_url': 'https://api.groq.com/openai/v1',
            'priority_weight': 40,
            'supports_streaming': True,
            'supports_json': True,
            'supports_vision': False,
            'supports_tool_calling': True
        },
        {
            'provider_id': 'ollama',
            'name': 'Ollama',
            'category': 'ai',
            'provider_type': 'local',
            'compatibility_profile': 'ollama_native',
            'lifecycle_state': 'CONFIGURED',
            'is_active': True,
            'base_url': 'http://localhost:11434',
            'priority_weight': 50,
            'supports_streaming': True,
            'supports_json': True,
            'supports_vision': True,
            'supports_tool_calling': False
        },
        {
            'provider_id': 'openai',
            'name': 'OpenAI',
            'category': 'ai',
            'provider_type': 'cloud',
            'compatibility_profile': 'openai_compatible',
            'lifecycle_state': 'UNCONFIGURED',
            'is_active': False,
            'base_url': 'https://api.openai.com/v1',
            'priority_weight': 60,
            'supports_streaming': True,
            'supports_json': True,
            'supports_vision': True,
            'supports_tool_calling': True
        },
        {
            'provider_id': 'anthropic',
            'name': 'Anthropic',
            'category': 'ai',
            'provider_type': 'cloud',
            'compatibility_profile': 'anthropic_native',
            'lifecycle_state': 'UNCONFIGURED',
            'is_active': False,
            'base_url': 'https://api.anthropic.com/v1',
            'priority_weight': 70,
            'supports_streaming': True,
            'supports_json': True,
            'supports_vision': True,
            'supports_tool_calling': True
        },
        {
            'provider_id': 'gemini',
            'name': 'Gemini',
            'category': 'ai',
            'provider_type': 'cloud',
            'compatibility_profile': 'gemini_native',
            'lifecycle_state': 'UNCONFIGURED',
            'is_active': False,
            'base_url': 'https://generativelanguage.googleapis.com/v1beta',
            'priority_weight': 80,
            'supports_streaming': True,
            'supports_json': True,
            'supports_vision': True,
            'supports_tool_calling': True
        }
    ]
    
    for p_data in providers_data:
        existing = Registry.search([('provider_id', '=', p_data['provider_id'])], limit=1)
        if existing:
            existing.write(p_data)
        else:
            Registry.create(p_data)
            
    print("Provisioned AI Providers Successfully.")

provision_providers(env)
env.cr.commit()
