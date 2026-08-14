import logging
import traceback
import sys

def main(env):
    print("=== Testing NVIDIA sync_catalog Exception ===")
    
    # Temporarily capture the error
    import io
    class CaptureLog(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(record.getMessage())

    logger = logging.getLogger('odoo.addons.nexora_studio.services.ai.catalog_service')
    cap = CaptureLog()
    logger.addHandler(cap)

    try:
        env['nexora.ai_provider_manager'].test_connection('nvidia')
    except Exception as e:
        print(f"Error testing nvidia: {e}")

    for msg in cap.records:
        if 'Catalog sync failed for provider nvidia:' in msg:
            print("FOUND EXCEPTION LOG:")
            print(msg)
            
    logger.removeHandler(cap)

if __name__ == '__main__':
    main(env)
    env.cr.rollback()
