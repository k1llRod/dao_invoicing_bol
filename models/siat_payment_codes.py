from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError


class SiatPaymentCodes (models.Model):
    _name = 'siat.payment.codes'
    _description = 'Modelos relacional entre diarios de pago y codigos SIAT'



    name = fields.Many2one('tipo.metodo.pago', string='Codigo Siat')
    journal_ids = fields.Many2many('account.journal', 'journal_siat_code_rel', 'siat_payment_code_id', 'journal_id', string='Diarios de Pago', domain="[('type', 'in', ['cash', 'bank'])]")
    active = fields.Boolean(default=True)

    string_journals_ids = fields.Char("Codigos de Diarios", readonly=True, compute="_string_journal_ids", store=True)

    @api.one
    @api.depends('journal_ids')
    def _string_journal_ids(self):
        """ Calculates Sub total"""
        self.string_journals_ids = self.get_journal_ids_str_format(self.journal_ids)

    def get_journal_ids_str_format(self, journal_ids):
        res = ""
        if len(journal_ids) > 0:
            lista = journal_ids.ids
            for j_id in sorted(lista):
                res += str(j_id)
        return res

    def get_payments_code(self, journal_ids):
        str_format = self.get_journal_ids_str_format(journal_ids) if journal_ids and len(journal_ids) else False
        siat_code = self.search([('string_journals_ids', '=', str_format)]) if str_format else False
        if siat_code:
            return siat_code.name
        else:
            raise ValidationError("No se encontro codigo de los diarios de pago recibidos")
