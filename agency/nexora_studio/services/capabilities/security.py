class SecurityLayer:
    def authorize(self, namespace: str, context: dict) -> bool:
        return True
        
    def inject_credentials(self, descriptor, context: dict) -> dict:
        return context