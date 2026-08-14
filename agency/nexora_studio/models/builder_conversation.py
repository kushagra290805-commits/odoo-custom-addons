# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json

class BuilderConversation(models.Model):
    _name = 'nexora.builder_conversation'
    _description = 'Builder Assistant Conversation Memory'
    _order = 'create_date desc'

    builder_session_id = fields.Many2one('nexora.builder_session', string='Builder Session', required=True, ondelete='cascade', index=True)
    messages_json = fields.Text(string='Messages JSON', default='[]', help="Stores the LLM-formatted conversation history.")
    
    @api.model
    def add_message(self, session_id, role, content, metadata=None):
        """Appends a message to the conversation for a session."""
        conv = self.search([('builder_session_id', '=', session_id)], limit=1)
        if not conv:
            conv = self.create({'builder_session_id': session_id})
            
        messages = json.loads(conv.messages_json or '[]')
        msg = {
            'role': role,
            'content': content,
            'timestamp': fields.Datetime.now().isoformat()
        }
        if metadata:
            msg['metadata'] = metadata
            
        messages.append(msg)
        conv.messages_json = json.dumps(messages)
        return conv

    @api.model
    def get_messages(self, session_id):
        conv = self.search([('builder_session_id', '=', session_id)], limit=1)
        if not conv:
            return []
        return json.loads(conv.messages_json or '[]')
