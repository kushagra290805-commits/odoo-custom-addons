from .protocol import ProtocolLayer

class TransportLayer:
    def __init__(self, protocol: ProtocolLayer):
        self.protocol = protocol
        
    def send(self, payload: dict):
        framed = self.protocol.serialize(payload)
        # Mock transmission
        return self.protocol.deserialize(framed)