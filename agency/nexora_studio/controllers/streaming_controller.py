import uuid
import queue
import logging
from odoo import http
from odoo.http import request, Response
from odoo.addons.nexora_studio.services.generation.streaming.streaming_service import StreamingService
from odoo.addons.nexora_studio.services.generation.streaming.transports import SSETransport

_logger = logging.getLogger(__name__)

class StreamingController(http.Controller):
    """
    HTTP Controller providing the Server-Sent Events (SSE) endpoint for generation streams.
    """
    
    @http.route('/nexora/stream/<string:generation_id>', type='http', auth='user', cors='*', methods=['GET'])
    def stream_generation(self, generation_id: str, **kwargs):
        """
        SSE endpoint to stream pipeline events to the client.
        Supports reconnects via the 'last_event_id' query parameter.
        """
        last_event_id = kwargs.get('last_event_id')
        client_id = str(uuid.uuid4())
        correlation_id = generation_id  # Assuming generation_id maps 1:1 to correlation_id for stream entry
        
        # Use a standard thread-safe Queue for SSE transport
        q = queue.Queue()
        transport = SSETransport(queue=q)
        
        streaming_service = StreamingService()
        
        # Register client
        session = streaming_service.register_client(
            generation_id=generation_id,
            correlation_id=correlation_id,
            client_id=client_id,
            transport=transport,
            last_event_id=last_event_id
        )

        def event_stream():
            try:
                while True:
                    # Blocking wait for the next event in the queue
                    # Use a timeout to occasionally check if client disconnected
                    try:
                        message = q.get(timeout=30)
                        if message is None:
                            # Sentinel value for stream closure
                            break
                        yield message
                    except queue.Empty:
                        # Queue timeout, just continue loop. The client disconnect will raise GeneratorExit.
                        continue
            except GeneratorExit:
                # Client disconnected from the browser
                _logger.info(f"Client {client_id} disconnected from stream {generation_id}")
            finally:
                streaming_service.unregister_client(session)

        # Odoo wrapper for SSE
        response = Response(event_stream(), content_type='text/event-stream')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Accel-Buffering'] = 'no' # Disable Nginx buffering
        response.headers['Connection'] = 'keep-alive'
        
        return response
