class CapabilityMiddleware:
    def process_request(self, namespace, context):
        pass
        
    def process_response(self, result, context):
        pass

class MiddlewarePipeline:
    def __init__(self):
        self.middlewares = []
        
    def add(self, middleware: CapabilityMiddleware):
        self.middlewares.append(middleware)
        
    def execute_pre(self, namespace, context):
        for m in self.middlewares:
            m.process_request(namespace, context)
            
    def execute_post(self, result, context):
        for m in reversed(self.middlewares):
            m.process_response(result, context)