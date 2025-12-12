# -*- coding: utf-8 -*-
from openerp import models, fields, api
from odoo.addons.account.models.account_payment import MAP_INVOICE_TYPE_PAYMENT_SIGN
from odoo.exceptions import UserError, ValidationError


class account_register_payments(models.TransientModel):
    _inherit = 'account.register.payments'

    eachinvoicehaspayment = fields.Boolean(string='One payment by invoice',
                                           help='If you want to create a payment per invoice, select this option, this method will also create a payment movement per invoice.',
                                           default=True)
    useinvdateforpayment = fields.Boolean(string='Payment date by invoice',
                                          help='If you want to use the invoice date to create each payment, select this option; otherwise the selected date will be used.',
                                          default=True)

    def get_payment_vals(self):
        """ Hook for extension """
        dic_base = super(account_register_payments, self).get_payment_vals()

        if self.eachinvoicehaspayment:
            # cambiar los keys del diccionario para especificar el id por invoice
            dic_base["invoice_ids"] = False
            dic_base["amount"] = False
            if self.useinvdateforpayment:
                dic_base["payment_date"] = False

        return dic_base

    @api.multi
    def create_payment(self):

        if self.eachinvoicehaspayment:
            payments = self.env['account.payment']
            dict_base = self.get_payment_vals()
            for inv in self._get_invoices():
                # seteamos los valores del diccionario segun los datos de la factura
                dict_payment = dict_base
                dict_payment["invoice_ids"] = [(4, inv.id, None)]
                dict_payment["amount"] = abs(inv.residual * MAP_INVOICE_TYPE_PAYMENT_SIGN[inv.type])
                # llamamos al metodo que nos devuelve el diccionario considerando nuestros campos adicionados al wizard
                dict_payment = self._dao_get_payment_dict(dict_payment, inv)
                # if self.useinvdateforpayment:
                #     dict_payment["payment_date"] = inv.date

                # creamos el invoice
                payment = self.env['account.payment'].create(dict_payment)
                # para poder concatenar varios id en un solo modelo no debemos manejarlo como un array de python
                # debemos usar el proceso de suma += de esta manera logramos un modelo con todos lo ids que querramos unir o concatenar
                payments += payment

            # hacemos el post de todos los pagos
            payments.post()
            return {'type': 'ir.actions.act_window_close'}
        else:
            return super(account_register_payments, self).create_payment()

        # payment = self.env['account.payment'].create(self.get_payment_vals())
        # payment.post()
        # return {'type': 'ir.actions.act_window_close'}

    # @api.onchange('payment_type')
    # def _onchange_payment_type(self):
    #     if self.payment_type:
    #         return {'domain': {'payment_method_id': [('payment_type', '=', self.payment_type)]}}
    #
    def _get_invoices(self):
        res = super(account_register_payments, self)._get_invoices()
        res = res.sorted(key=lambda inv: inv.date_invoice)
        return res

    def _dao_get_payment_dict(self, dict_payment, inv):
        """modularizamos la obtencion y aplicacion de logica DAO para que otros de nuestros modulo puedan extendeer sin problema
        la obtencion del diccionario de pagos desde facturas"""
        if self.useinvdateforpayment:
            dict_payment["payment_date"] = inv.date
        return dict_payment
    #
    # @api.model
    # def default_get(self, fields):
    #     rec = super(account_register_payments, self).default_get(fields)
    #     context = dict(self._context or {})
    #     active_model = context.get('active_model')
    #     active_ids = context.get('active_ids')
    #
    #     # Checks on context parameters
    #     if not active_model or not active_ids:
    #         raise UserError(_("Programmation error: wizard action executed without active_model or active_ids in context."))
    #     if active_model != 'account.invoice':
    #         raise UserError(_("Programmation error: the expected model for this action is 'account.invoice'. The provided one is '%d'.") % active_model)
    #
    #     # Checks on received invoice records
    #     invoices = self.env[active_model].browse(active_ids)
    #     if any(invoice.state != 'open' for invoice in invoices):
    #         raise UserError(_("You can only register payments for open invoices"))
    #     if any(inv.commercial_partner_id != invoices[0].commercial_partner_id for inv in invoices):
    #         raise UserError(_("In order to pay multiple invoices at once, they must belong to the same commercial partner."))
    #     if any(MAP_INVOICE_TYPE_PARTNER_TYPE[inv.type] != MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type] for inv in invoices):
    #         raise UserError(_("You cannot mix customer invoices and vendor bills in a single payment."))
    #     if any(inv.currency_id != invoices[0].currency_id for inv in invoices):
    #         raise UserError(_("In order to pay multiple invoices at once, they must use the same currency."))
    #
    #     total_amount = sum(inv.residual * MAP_INVOICE_TYPE_PAYMENT_SIGN[inv.type] for inv in invoices)
    #     communication = ' '.join([ref for ref in invoices.mapped('reference') if ref])
    #
    #     rec.update({
    #         'amount': abs(total_amount),
    #         'currency_id': invoices[0].currency_id.id,
    #         'payment_type': total_amount > 0 and 'inbound' or 'outbound',
    #         'partner_id': invoices[0].commercial_partner_id.id,
    #         'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type],
    #         'communication': communication,
    #     })
    #     return rec
    #
    # def get_payment_vals(self):
    #     """ Hook for extension """
    #     return {
    #         'journal_id': self.journal_id.id,
    #         'payment_method_id': self.payment_method_id.id,
    #         'payment_date': self.payment_date,
    #         'communication': self.communication,
    #         'invoice_ids': [(4, inv.id, None) for inv in self._get_invoices()],
    #         'payment_type': self.payment_type,
    #         'amount': self.amount,
    #         'currency_id': self.currency_id.id,
    #         'partner_id': self.partner_id.id,
    #         'partner_type': self.partner_type,
    #     }
    #
    # @api.multi
    # def create_payment(self):
    #     payment = self.env['account.payment'].create(self.get_payment_vals())
    #     payment.post()
    #     return {'type': 'ir.actions.act_window_close'}


class account_payment(models.Model):
    """
    Extendemos el Model account.payment para que tb herede de dao_account_cancel base
    Nos basamos en extensiones de la comunidad que extienen por ejemplo el res.partner pero heredando tb de barcode.generate.mixin
    notar que debemos mantener el mismo _name inicial.
    _name = 'res.partner'
    _inherit = ['res.partner', 'barcode.generate.mixin']
    """
    # Mantenemos el mismo name original del primer Inherits
    _name = 'account.payment'
    _inherit = ['account.payment', 'dao_account.cancel']

    # extendemos el campo estado de pagos para agregar nuestro estado de cancelacion
    state = fields.Selection(selection_add=[('dao_cancelled', 'Cancelled')])

    @api.multi
    def cancel(self):
        """extendemos el metodo cancel de payment, para aplicar nuestra logica de cancelacion
        mediante un asiento de reversion, y la automatizacion de la conciliacion del movimiento
        original del pago y el asiento de reversion, en sus lineas reconciliables"""
        dao_paymentcancel = self.get_use_cancel_with_reversal()
        # # validamos que la configuracion de cancelacion de pagos este en verdadero
        # if dao_paymentcancel:
        #     # recorremos todos los pagos
        #     for rec in self:
        #         # recorremos las lineas para romper la conciliacion existente de los movimientos a los que pertenecen
        #         moves = rec.move_line_ids.mapped('move_id')
        #         if moves:
        #             for move in moves:
        #                 move.line_ids.remove_move_reconcile()
        #             # move.button_cancel()
        #             # en ves de cancelar el movimientos lo que haremos es crear un movimiento de reversion
        #             reverse_move = move.reverse_moves()
        #             # validamos que se haya creado el movimiento de reversion
        #             if reverse_move:
        #                 # buscamos los movimientos que su cuenta sea reconciliable
        #                 payment_move_lines = self.env['account.move.line'].search([('payment_id', '=', rec.id),
        #                                                                            ('account_id.reconcile', '=', True)])
        #                 # validamos que las lineas sean 2
        #                 if payment_move_lines and len(payment_move_lines) == 2:
        #                     # ejecutamos el metodo de reconciliacion de las lineas
        #                     payment_move_lines.reconcile()
        #                 else:
        #                     return False
        #             else:
        #                 return False
        #         else:
        #             return False
        #     # cambiamos el estado del pago a cancelado
        #     rec.state = 'dao_cancelled'
        # else:
        #     # caso contrario ejecutamos la base
        #     super(account_payment, self).cancel()
        # import pudb;pudb.set_trace()
        # verificamos si usamos el DAO_CANCEL metodo o usamos el basico CANCEL segun si el journal tiene permitido CANCELA - BORRRA account.moves.
        if dao_paymentcancel:
            # Antes de ejecutar el metodo de romper conciliacion - movimiento reversion - conciliacion
            # vemos si el pago esta asociado a un pago action_invoice_re_open()
            # podemos crear una funcion de obtener ids referenciales, por ejemplo para invoice y ya en hr extender la funcion y el diccionario adicionar key de payslips
            # tomar en cuenta que reopen es solamente usando para invoices que esten pagadas, otros estados daria excepcion.
            # ademas que si la factura esta cancelada y queremos cancelar el pago, no tenemos para que reabrir la factura.

            # TOMAR en cuenta: INVOICE tiene el compute RESIDUAL AMOUNT (invioice._compute_residual) que tiene dependencia a account.move ('move_id.line_ids.amount_residual')
            # y al romper conciliacion en dao_cancel, el amount_residual cambia, por tanto accoount.invoice._compute_residual se ejecuta y por ende account.invoice.reconciled cambia de false a true por ende se ejecuta
            # el account.invoice.def _write y este a su vez el action_invoice_re_open si es que la factura tiene el estado pagado, si la factura esta cancel no pasa nada.
            # despues deberiamos usar algo parecido en payslip ...?

            self.dao_cancel()
        else:
            # caso contrario ejecutamos la base
            super(account_payment, self).cancel()

        # en Ambos casos al final cambiamos el estado del account.payment a CANCELADO
        self.set_cancel_state()

    def get_move_id_for_cancel(self):
        """
        Overridden de la funcion BASE.

        Para poder implementar y ejecutar dao_cancel cada model tiene que saber como obtiene los account.moves_ids
        """
        self.ensure_one()
        return self.move_line_ids.mapped('move_id')

    def get_use_cancel_with_reversal(self):
        """
        Verifica si tenemos especificado en la configuracion de settings si usamos la lógica DAO CANCEL, es decir usando REVERSAL y Conciliando, en lugar de la lógica BASE que es la ELIMINACIÓN de movimientos contables.
        dao_paymentcancel = self.env['ir.values'].get_default('account.config.settings', 'dao_payments_cancel')
        """
        return self.env['ir.values'].get_default('account.config.settings', 'dao_payments_cancel')

    @api.multi
    def set_cancel_state(self):
        """
        Establece el ESTADO CANCELADO al PAGO.
        """
        self.write({'state': 'dao_cancelled'})

# extencion de post para el cambion de estado a pagado
#     @api.multi
#     def post(self):
#         # todo: debemos cambiar la manera de validar la generacion de factura siat desde pago
#         for payment in self:
#             for invoice in payment.invoice_ids:
#                 if invoice.siat_bol_generated == False:
#                     nro_tarjeta = self.first_number_card + '00000000' + self.last_number_card if payment.journal_id.it_card else False
#                     invoice.action_siat_push_invoice(payment.journal_id.metodo_pago_id, nro_tarjeta)
#         super(account_payment, self).post()
