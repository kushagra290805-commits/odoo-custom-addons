# -*- coding: utf-8 -*-
from odoo import models, fields

class GenerationStageOverride(models.Model):
    _inherit = 'nexora.generation_stage'

    stage_type = fields.Selection(
        selection_add=[
            ('planner_blueprint', 'Planner Blueprint'),
            ('planner_execution', 'Planner Execution')
        ],
        ondelete={
            'planner_blueprint': 'set default',
            'planner_execution': 'set default'
        }
    )
