import logging
import sys
import traceback

def main(env):
    Registry = env['nexora.provider.registry'].__class__
    original_write = Registry.write

    def traced_write(self, vals):
        if 'catalog_sync_status' in vals:
            for rec in self:
                old_val = rec.catalog_sync_status
                new_val = vals['catalog_sync_status']
                print(f"\n[TRACE] catalog_sync_status changing for {rec.provider_id}: {old_val} -> {new_val}")
                traceback.print_stack(limit=15)
        return original_write(self, vals)

    Registry.write = traced_write

    print("\n=== Testing NVIDIA ===")
    try:
        env['nexora.ai_provider_manager'].test_connection('nvidia')
        env['nexora.ai_catalog_service'].sync_catalog('nvidia')
    except Exception as e:
        print(f"Error testing nvidia: {e}")
        traceback.print_exc()

    print("\n=== Restoring write ===")
    Registry.write = original_write

if __name__ == '__main__':
    main(env)
    env.cr.rollback()
