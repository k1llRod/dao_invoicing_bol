# -*- coding: utf-8 -*-

from openerp import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError


class AccountMove(models.Model):
    """
        Extencion del modelo account.move
    """

    _inherit = 'account.move'

    @api.multi
    def button_cancel(self):
        """
            Extendemos el metodo del boton de cancelacion de asientos para restringir el acceso por grupo

        """
        # Se verifica que el usuario tenga el grupo  que creamos
        user_group = self.env['res.users'].has_group('dao_invoicing_bol.dao_adv_acc_permissions')
        if not user_group:
            raise UserError(_('No tiene permiso para cancelar este asiento, contactese con su administrador.'))
        # en caso de tener el grupo llamamos a la base
        return super(AccountMove, self).button_cancel()


class AccountMoveLine(models.Model):
    """
    Extendemos el Account.move.line para cambiar el orden que se especifica en el modulo BASE.
    Por concepto de exposicion, primero deberia mostrarse el tema de DEBITOS

    Odoo en el módilo BASE indica: _order = "date desc, id desc"

    Por tanto cuando se hace un movimiento contable, generalmente en BOLIVIA primero registran el DEBITO
    y después el HABER, pero como order by tiene id desc se ve al reves al momento de guardar.

    cambiaremos para que sea ASC, y tener el concepto de EXPOSICION BOLIVIA
    """
    _inherit = "account.move.line"
    # Cambiamos el SORT para tener el ID asc
    _order = "date desc, id asc"