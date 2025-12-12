# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class WizardPushSiatInvoice(models.TransientModel):
    """
    This wizard will confirm the all the selected draft invoices
    """

    _name = "wizard.push.siat.invoice"
    _description = "Push Siat Invoice"

    @api.multi
    def invoice_push(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []

        for record in self.env['account.invoice'].browse(active_ids):
            if record.state != 'open':
                raise UserError(_("Selected invoice(s) cannot be pushed as they are not in open state."))
            record.action_siat_push_invoice()
        return {'type': 'ir.actions.act_window_close'}