# -*- coding: utf-8 -*-
from openerp import fields, api, models, _
from openerp.exceptions import ValidationError
import ast


class CancelInvoiceSiat(models.TransientModel):
    _inherit = "cancel.invoice.siat"

    motivo_anulacion_id = fields.Many2one('motivo.anulacion', string='Motivo de anulacion')

    def action_assign_cancel_invoice_siat(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        obj = self.env['siat.servicio.facturacion']
        invoice_ids = self.env['account.invoice'].browse(active_ids)
        if any(inv.state == 'paid' for inv in invoice_ids):
            raise ValidationError('Debe romper conciliacion con los pagos antes de anular alguna factura')
        if any(inv.siat_status == 'ANULACION CONFIRMADA' for inv in invoice_ids):
            raise ValidationError('LA factura ya se encuentra ANULADA')

        for record in invoice_ids:
            res = obj.anulacion_factura(company_id=record.company_id,
                                        code_doc_sector=record.siat_codigo_documento_sector,
                                        code_emition=record.siat_codigo_emision.codigo_clasificador,
                                        cuis=record.siat_invoice_channel,
                                        type_invo_doc=str(record.siat_invoice_channel.type_factura.codigo_clasificador),
                                        code_motivo=self.motivo_anulacion_id.codigo_clasificador,
                                        branch_code=record.siat_invoice_channel.branch_code,
                                        cuf=record.siat_cuf)
            if res['transaccion']:
                siat_codigo_estado = self.env['mensajes.servicios'].search([('codigo_clasificador', '=', res['codigoEstado'])], limit=1)
                # siat_data_dict = ast.literal_eval(str(record.siat_data_dict))
                # siat_data_dict['siat_codigo_estado'] = res['codigoDescripcion']
                # record.siat_data_dict = siat_data_dict
                record.update({'siat_status': str(res['codigoDescripcion']),
                               'siat_codigo_estado': siat_codigo_estado.id})
                invoice_ids.action_cancel()
                record.action_send_email_siat_cancel()
