# -*- coding: utf-8 -*-
# import logging
from openerp import api, fields, models, _
from openerp.exceptions import ValidationError

# _logger = logging.getLogger(__name__)


class res_partner(models.Model):
    _inherit = 'res.partner'

    # Columnas
    nit = fields.Char('NIT', default='0', size=15, required=True, help='Tax Identification Number idenfy unequivocally that allows taxpayers and will consist of control codes issued by the tax authorities, depending on the type of taxpayer.')
    dao_uni_personal_flag = fields.Boolean(string='Razon Social', default=False,
                                           help="if the company is unipersonal, we must registry the Business name.\n\n"
                                                "For example: The Company name (Tradename) is 'MY COMPANY' but the Bussiness names is 'CARLOS PEREZ'.\n\n"
                                                "* The invoice printed shows:\n"
                                                "MY COMPANY\n"
                                                "DE: CARLOS PEREZ")
    dao_uni_personal_name = fields.Char(string='Razon social Name',
                                        help="If the company is unipersonal type, must fill this field.\n\n"
                                             "Example: 'CARLOS PEREZ'\n\n"
                                             "* If Company name (Tradename) is 'MY COMPANY', the Bussiness names is 'CARLOS PEREZ'.\n"
                                             "* This field is really important for the 'LIBRO DE COMPRAS'.\n\n"
                                             "* The invoice printed shows:\n"
                                             "MY COMPANY\n"
                                             "DE: CARLOS PEREZ\n\n"
                                             "* We must registry the name without the 'DE:' text")
    dao_cpl_personal = fields.Char(string='Complemento',
                                   help="Campo a ser usado por el completo del NIT de ser necesario")

    # Constraints
    @api.one
    @api.constrains('nit')
    def _check_nit(self):
        if self.nit and not self.nit.isdigit() and self.type_doc_identidad.codigo_clasificador not in [2,3,4]:
            raise ValidationError(_('NIT can only contain digits!'))

    @api.one
    @api.constrains('dao_uni_personal_name', 'dao_uni_personal_flag')
    def _check_dao_uni_personal_name(self):
        if self.dao_uni_personal_flag and not self.dao_uni_personal_name:
            raise ValidationError(_('If uni-personal company flag is selected, fill uni-personal name is mandatory'))

    @api.one
    @api.constrains('dao_cpl_personal')
    def _check_dao_cpl_personal(self):
        if self.type_doc_identidad.codigo_clasificador != 1 and self.dao_cpl_personal:
            raise ValidationError('Solo puede registrar complemento para documentos de identidad "Cedula de Identidad"')

