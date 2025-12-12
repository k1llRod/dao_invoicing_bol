# -*- coding: utf-8 -*-
from openerp import fields, api, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.siat_sin_bolivia.tools import siat_tools as st


class RegisterEventoSignificativo(models.TransientModel):
    _inherit = "register.evento.significativo"

    @api.model
    def default_get(self, fields):
        rec = super(RegisterEventoSignificativo, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        invoices = self.env[active_model].browse(active_ids)

        if len(active_ids) == 0:
            raise ValidationError("La cantidad de facturas a procesar es cero")
        if any(invoice.state not in ['open', 'paid'] for invoice in invoices):
            raise ValidationError("Las facturas tienen que estar validades")
        if any(invoice.siat_offline != True for invoice in invoices):
            if any(invoice.siat_bol_sale_type != 'manual' for invoice in invoices):
                raise ValidationError("Se debe seleccionar facturas emitidas fuera de linea")
        if len(list(set(invoices.mapped('siat_codigo_sucursal')))) > 1:
            raise ValidationError("Las facturas deben ser de la misma sucursal")
        if len(list(set(invoices.mapped('siat_cafc')))) > 1:
            raise ValidationError("Las facturas deben ser del mismo CAFC")
        if len(list(set(invoices.mapped('siat_codigo_punto_venta')))) > 1:
            raise ValidationError("Las facturas deben ser del mismo punto de venta")
        if len(list(set(invoices.mapped('siat_cufd')))) > 1:
            raise ValidationError("Las facturas deben ser del mismo CUFD")
        if len(active_ids) > 500:
            raise ValidationError("No se puede procesar mas de 500 facturas")

        rec.update({'siat_cuis_id': invoices[0].siat_invoice_channel.id,
                    'company_id': invoices[0].company_id.id,
                    'cuis': invoices[0].siat_cuis,
                    'date_start': st.iso_strdt_to_dt_odoo_utc(min([x.siat_fecha_emision for x in invoices]), self.env.user.tz).strftime("%Y-%m-%d %H:%M:%S"),
                    'date_end': st.iso_strdt_to_dt_odoo_utc(max([x.siat_fecha_emision for x in invoices]), self.env.user.tz).strftime("%Y-%m-%d %H:%M:%S"),
                    'cufd': invoices[0].siat_cufd,
                    'siat_cafc': invoices[0].siat_cafc,
                    })
        return rec