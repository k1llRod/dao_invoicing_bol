# -*- coding: utf-8 -*-

from odoo import fields, models, api


class AccountConfigSettings(models.TransientModel):
    """
    Extender el model account.config.settings de Account.
    Adicionar configuración para instalar el modulo dao_invoicing_multi_dosificacion_bol desde settings de accounts.

    Es decir, es como un shortcut a instalar este módulo sin necesidad de ir a app -> buscar este módulo y darle instalar.

    Tomar la misma funcionalidad de pos y pos restaurant
    """
    _inherit = 'account.config.settings'

    # # Adicionamos columna
    # # Tomar en cuenta que el nombre de la columna empieza con module_ para que ODOO interprete esta configuracion e instale el modulo dao_account_groups_pos_bol cuando el usuario seleccione el radio button en settings.
    # module_dao_invoicing_multi_dosificacion_bol = fields.Selection([(0, "Simple"),
    #                                                                 (1, "Activar Múltiple Dosificación.")
    #                                                                 ],
    #                                                                string="Tipo Dosificación",
    #                                                                help=" Este módulo adiciona la característica de múltiple dosificación para emitir facturas:\n\n"
    #                                                                     " * Poder tener Dosificaciones por sucursales:\n"
    #                                                                     " * Poder tener Dosificaciones por Rubros\n"
    #                                                                     " * Poder tener Dosificaciones por Rubros y sucursales",
    #                                                                )
    #
    # #se adiciona el campo para deshabilitar la configuracion del control de la fecha
    dao_date_invoice_future = fields.Boolean(string="Permitir ingreso de Facturas con Fecha Adelantada",
                                             default=False,
                                             help="Permite ingresar facturas con fechas adelantadas")

    # se adiciona el campo para habilitar el uso de nuestra logica de cancelacion de pagos mediante reversion de asiento contrable
    # y conciliacion automatica
    dao_payments_cancel = fields.Boolean(string="Cancelar pagos con reversión",
                                         default=False,
                                         help="Permite realizar la cancelación de un pago mediante la reversión de su asiento contable")

    @api.multi
    def set_default_dao_date_invoice_future(self):
        IrValues = self.env['ir.values']
        IrValues.set_default('account.config.settings', 'dao_date_invoice_future', self.dao_date_invoice_future)

    @api.model
    def get_default_dao_date_invoice_future(self, fields):
        return {
            'dao_date_invoice_future': self.env['ir.values'].get_default('account.config.settings', 'dao_date_invoice_future')
        }

    @api.multi
    def set_default_dao_payments_cancel(self):
        IrValues = self.env['ir.values']
        IrValues.set_default('account.config.settings', 'dao_payments_cancel', self.dao_payments_cancel)

    @api.model
    def get_default_dao_payments_cancel(self, fields):
        return {
            'dao_payments_cancel': self.env['ir.values'].get_default('account.config.settings',
                                                                     'dao_payments_cancel')
        }
