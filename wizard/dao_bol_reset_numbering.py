#-*- coding: utf-8 -*-
from openerp import models, api, _
#from openerp import UserError
from odoo.exceptions import UserError
from openerp.exceptions import ValidationError


class DaoResetNumberingWizard(models.TransientModel):
    """
    Clase wizard para resetear secuencias de factura de compañias
    """
    _name = "dao.reset.numbering"

    @api.multi
    def reset_numbering_invoice(self):
        """
        Resetea la numeracion de la secuencia facturas de una o varias compañias especificadas
        :return: None
        """
        context = dict(self._context or {})
        active_ids = context.get('active_ids', [])

        # Validar si el current user tiene acceso a las companies especificadas
        not_in = [item for item in active_ids if item not in self.env.user.company_ids.ids]
        if not_in and len(not_in) > 0:
            raise UserError(_('This user have not acces to some companies.'))

        sequence_code = "dao.invoicing.bol.number"
        company_ids = active_ids + [False]
        # Trae la secuencia del ir.sequence
        seq_ids = self.env['ir.sequence'].search(['&', ('code', '=', sequence_code), ('company_id', 'in', company_ids)])

        if not seq_ids:
            raise ValidationError("No ir.sequence has been found for code '%s'." % sequence_code)

        # Obtenemos en un array preferred_sequences todas las secuencias que tengan company
        # y sean las que se especifica en active_ids del wizard
        preferred_sequences = [s for s in seq_ids if s.company_id and s.company_id.id in active_ids]

        if preferred_sequences and len(preferred_sequences) > 0:
            # se obtiene el preferred_sequences correcto para resetear el numero
            for seq in preferred_sequences:
                self._reset_number_next_actual(seq)
        else:
            # No se tiene preferred_sequence, por tanto puede ser que se tenga seq.ids pero sin company especificada
            # Por tanto solo actualizamos la primera secuencia que se encuenta en seq_ids
            self._reset_number_next_actual(seq_ids[0])

    def _reset_number_next_actual(self, seq):

        """
        Actualiza el valor del number_next_actual del model ir.sequence
        :param seq: referencia al ir.sequence que se quere resetear
        :return: True
        
        Lo hacemos con SUDO para evitar que el usuario si o si tenga que tener el perfil administration/settings
        """
        seq.sudo().number_next_actual = 1
        return True
