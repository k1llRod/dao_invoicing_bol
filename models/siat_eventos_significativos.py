# -*- coding: utf-8 -*-
from odoo import fields, models, api


class SiatEventosSignificativos(models.Model):

    _inherit = 'siat.eventos.significativos'

    invoice_ids = fields.One2many('account.invoice', 'siat_evento_significativo_id')