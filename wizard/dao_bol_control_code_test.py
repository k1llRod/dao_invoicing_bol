# -*- coding: utf-8 -*-
from openerp import api, fields, models, _
# from openerp.exceptions import UserError


class DaoControlCodeTestWizard(models.TransientModel):
    """
    Clase para poder usar el WIZARD y generar un codigo de control de pruebas.
    Se hereda de models.TransientModel que permite guardar temporalmente los atributos de esta clase en la BD segun lo que indique el usuario en el WIZARD.
    Despues de generar el codigo de control, ODOO tiene la logica de borrar estos datos temporales.
    Este models.TransientModel almacena temporalmente para que se pueda usar el concepto de WIZARD, mientras que el models.AbstractModel no almacena nada en la BD, todo esta en memoria para generar el codigo de control.
    Odoo Tiene en Settings -> Scheduled Action -> Auto Vacuum Internal Data, esta tarea se encarga de eliminar los TransientModels antiguos.
    Primero se muestra un WIZARD donde el usuario indican los datos necesarios para generar un Código de Control.
    Después se muestrar en otro VIEW la respuesta del proceso con el valor del codigo de Control.

    Basandonos en la inicializacion de la clase dao_bol_control.py:
    def __init__(self, strAuthNumber, intInvoiceNumber, intClientNIT, intDate, intTotalAmount, strKEY)
    """
    _name = "dao.control.code.test.wizard"
    _description = "Control Code Test Wizard"

    client_nit = fields.Char('NIT', default='0', size=15, required=True, help='Tax Identification Number idenfy unequivocally that allows taxpayers and will consist of control codes issued by the tax authorities, depending on the type of taxpayer.')
    auth_nro = fields.Char(string='Authorization Number', size=15, required=True, default='', help='Authorization number assigned by the SIN.')
    proportion_key = fields.Text(string='Proportion Key', required=True, default='', help='Key assigned by the SIN to the dosage requested by the taxpayer. It is the private key used by the cryptographic algorithm.')
    invoice_nro = fields.Char(string='Invoice number', required=True, size=10, default='1', help='Invoice Number (Sequence)')
    amount = fields.Float(string='Amount', required=True, default=0)
    invoice_date = fields.Date(string='Invoice Date', default=fields.Date.today())
    # Adicionamos una columna donde almacenamos el codigo de control generado
    control_code = fields.Char(string='Control Code', readonly=True, size=17, help='It is a alphanumeric data generated and printed by a computerized billing, time to issue an invoice.')

    @api.multi
    def generate_control_code(self):
        """
        Metodo que se ejecuta al momento que el usuario presiona el botón 'Generar' del WIZARD para generar código de control de prueba.
        Basicamente en base a los datos que el usuario indica en el WIZARD, se genera un código de control y se retorna la navegación a otro wizard para mostrar el código de control generado.
        """
        self.ensure_one()
        # raise UserError(_('Metodo no implementado'))

        # Obtenemos la instancia al current company, es decir a la company actual
        # Fetching record using XML id
        # id = self.env.ref('base.main_company').id
        # objCompany = self.env['res.company'].browse([id])

        # La mejor manera creo q seria usando _company_default_get del model res.company, indicandole el nombre de este modulo
        # en este caso usaremos el nombre de modulo de account.invoice que ya lo usamos antes y es el modulo BASE del ERP
        company = self.env['res.company']._company_default_get('account.invoice')

        # Generamos el Codigo de Control
        # usamo el metodo : get_control_code_with_key(self, strTransactionDate, dblAmount, strAuthNumber, strInvoiceNumber, strNIT, strProportion_key)
        # del model res.company
        strControlCode = company.get_control_code_with_key(self.invoice_date, self.amount, self.auth_nro, self.invoice_nro, self.client_nit, self.proportion_key)

        # Guardamos el control code, en la columna self.control_code
        self.write({'control_code': strControlCode or ''})

        # Obtenemos el ID del VIEW (wizard - mensaje) que indica que se genero codigo de control
        view_id = self._get_test_wizard_done_id()

        # print "K32 DaoControlCodeTestWizard.generate_control_code -> self.id", self.id
        # print "K32 DaoControlCodeTestWizard.generate_control_code -> view_id", view_id

        # Retornamos el Diccionario con los datos para indicar al usuario el codigo de control generado.
        return {
            'name': _('CONTROL CODE GENERATED'),
            # Pasamo el ID de self.id xq este model tiene el csv_data para poder ser descargado.
            # Tomar en cuenta que este model es Trasient, es decir se almacena temporalmente los datos durante un determinado tiempo en la BD.
            'res_id': self.id,
            # Colocamos como model el mismo que pusimos al WIZARD
            'res_model': 'dao.control.code.test.wizard',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'view_id': view_id,
            'view_mode': 'form',
            'view_type': 'form',
        }

    def _get_test_wizard_done_id(self):
        """
        Obtiene el ID del VIEW que es el WIZARD que muestra como resultado el codigo de control generado.
        """
        return self.env['ir.ui.view'].search([('name', '=', 'dao_control_code_test_wizard_done')]).id
