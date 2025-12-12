# -*- coding: utf-8 -*-
import logging
# from operator import itemgetter
# import time
# from datetime import datetime
# from openerp.osv import osv, fields
from openerp import api, fields, models, _
# from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
# from openerp.http import request
from openerp.exceptions import ValidationError
# from dao_bol_control_code import BolTransaction as BOL
from dao_bol_control_code import BolTransactionV7 as BOL
from datetime import datetime

# Manejar precision decimal para el monto en el codigo de control
# import openerp.addons.decimal_precision as dp

_logger = logging.getLogger(__name__)


class res_company(models.Model):
    """
    Extension de la clase res.company para adicionar los campos necesarios para emitir facturas con la normativa Boliviana establecidad por el SIN
    """
    _inherit = "res.company"

    # @api.one
    # def _compute_seq_number(self):
    #     sequence_code = "dao.invoicing.bol.number"
    #     company_ids = [self.id] + [False]
    #     seq_ids = self.env['ir.sequence'].search(['&', ('code', '=', sequence_code), ('company_id', 'in', company_ids)])
    #
    #     # no se necesita validar y lanzar la excepción, si no existe, el compute que retorne 0
    #     # xq cuando creemos un multicompany nos dará error y no nos dejará modificar esta.
    #     # if not seq_ids:
    #     #     raise ValidationError("No ir.sequence has been found for code '%s'. Please make sure a sequence is set for current company." % sequence_code)
    #
    #     if seq_ids:
    #         # Cual debo usar?, tomar encuenta :
    #         # Como se usa el company in [1, False], podria que el primer sea el de la company, o pueden haber varios que no tiene company
    #         # preferred_sequences = [s for s in seq_ids if s.company_id and s.company_id.id == force_company]
    #         preferred_sequences = [s for s in seq_ids if s.company_id and s.company_id.id == self.id]
    #         # De preferred_sequences pueden ser varios si pusieron el mismo company_id, por tanto usaria el primero
    #         # Pero si no tengo ningun preferred_sequences, utilizo el primer seq que tengo en el array seq_ids
    #         seq_id = preferred_sequences[0] if preferred_sequences else seq_ids[0]
    #
    #         # Coloco el valor del number_next_actual al campo calculado (computed)
    #         self.seq_number = seq_id.number_next_actual
    #     else:
    #         self.seq_number = 0

    # columnas para adicionar a la clase base
    # seq_number = fields.Integer(compute='_compute_seq_number', string="Number Sequence Invoice", store=False)
    # bol_invoice_auth_nro = fields.Char(string='Authorization Number', size=15, required=True, default='', help='Authorization number assigned by the SIN.')
    # bol_invoice_proportion_key = fields.Text(string='Proportion Key', required=True, default='', help='Key assigned by the SIN to the dosage requested by the taxpayer. It is the private key used by the cryptographic algorithm.')
    # bol_invoice_date_limit = fields.Date(string='Deadline emition', required=True, default=fields.Date.today(), help='Deadline for emiting invoices')
    # bol_invoice_caption_1 = fields.Text(string='Caption 1', help='First caption for the invoice (RND10-0025-14-SFV)', default='"Esta factura contribuye al desarrollo del país. El uso ilícito de esta será sancionado de acuerdo a ley"')
    # bol_invoice_caption_2 = fields.Text(string='Caption 2', help='Second caption for the invoice (RND10-0025-14-SFV)', default='Ley Nro. 453: "El proveedor debe brindar atención sin discriminación, con respeto, calidez y cordialidad a los usuarios y consumidores."')
    # Adicionamos la columna para manejar el RUBRO o categoria para la company en base al NIT de esta registrado en el SIN
    # bol_invoice_category = fields.Char(string='Category', required=True, size=200, default='Indefinido', help='NIT category for the company')
    # Columna funcional para poder interactuar con el NIT de res_partner que representa la company.
    # bol_nit = fields.Char('NIT', related='partner_id.nit', default='0', size=15, required=True, help='Tax Identification Number idenfy unequivocally that allows taxpayers and will consist of control codes issued by the tax authorities, depending on the type of taxpayer.')
    #
    # bol_invoice_gasoline_percentage = fields.Float(string='% not subject to tax credit', digits=(3, 2), required=True, default=30.0, help='Percentage not subject to tax credit (Gasoline).')

    # bol_is_rts = fields.Boolean(string="Régimen Tributario Simplificado (RTS)",
    #                             default=False,
    #                             help="El Servicio Nacional de Impuestos de Bolivia, exime de emitir facturas a personas que tengan un capital menor o igual un determinado monto establecido por ley. \n\n"
    #                                  "El Régimen Tributario Simplificado (RTS) es lo que el SIN cataloga como personas permitidas a no emitir facturas.\n"
    #                                  "Caso contrario el Régimen es el GENERAL.")

    # bol_is_rtc = fields.Boolean(string="Régimen Tasa Cero en IVA (RTC)",
    #                             default=False,
    #                             help="Sujetos Pasivos o Terceros Responsables que se encuentren alcanzados por el Régimen Tasa Cero en IVA \n"
    #                                  "para emitir Facturas con la característica especial 'Tasa Cero – Sin Derecho a Crédito Fiscal'\n\n"
    #                                  "Transporte Internacional de Carga por Carretera, Venta de Libros, Turismo y otras establecidas por Ley ")
    # Segun el Articulo 64. (Tasa Cero - IVA).
    # se debe tener por un titulo para la factura y subtitulo indicando que no tiene credito fiscal y un segundo subtitulo
    # para el caso de los espectaculos publicos eventuales
    # bol_rtc_title = fields.Text(string='RTC Título',
    #                             help='Título: Consignar el tipo de Factura, Nota Fiscal o Documento Equivalente \n'
    #                             "Es decir: 'FACTURA', 'FACTURA POR TERCEROS', 'FACTURA CONJUNTA', 'RECIBO DE ALQUILER'\n"
    #                             "'FACTURA COMERCIAL DE EXPORTACIÓN', 'FACTURA COMERCIAL DE EXPORTACIÓN EN LIBRE CONSIGNACIÓN'\n"
    #                             "'FACTURA TURÍSTICA', 'FACTURA ARTISTAS NACIONALES', 'NOTA CRÉDITO - DÉBITO', según corresponda.")
    # bol_rtc_subtitle1 = fields.Text(string='RTC SubTítulo',
    #                                 help="Subtítulo: Consignar las características especiales, es decir:\n"
    #                                 "'SIN DERECHO A CRÉDITO FISCAL', 'TASA CERO - SIN DERECHO A CRÉDITO FISCAL',\n"
    #                                 "'TASA CERO - SIN DERECHO A CRÉDITO FISCAL, LEY No 366, DEL LIBRO Y LA LECTURA',\n"
    #                                 "ZONA FRANCA - SIN DERECHO A CREDITO FISCAL, según corresponda.")
    # bol_rtc_subtitle2 = fields.Text(string='RTC SubTítulo 2',
    #                                 help="Subtítulo: Para el caso de los espectáculos públicos eventuales se deberá consignar:\n"
    #                                 "'ESPECTÁCULO PÚBLICO EVENTUAL'.")

    # Adicionamos un campo para que podamos especificar que titulo colocar para comprobantes de pagos en caso de usar facturacion de Bolivia.
    # bol_receipt_title = fields.Char(string='Título Comprobante',
    #                                 required=True,
    #                                 size=50,
    #                                 default='RECIBO',
    #                                 help='Título a colocar en el comprobante del PAGO en caso de configurar la compañia como RTS, o al vender sin emitir una factura.')

    # bol_entity_title = fields.Char(string='Entity Title',
    #                                required=False,
    #                                size=50,
    #                                default='',
    #                                help="Title for the company entity, example: \n"
    #                                "'CASA MATRIZ' or 'SUCURSAL 1'")
    #
    # bol_nombre_comercial = fields.Char(string='Trade name',
    #                                    required=False,
    #                                    size=200,
    #                                    default='',
    #                                    help="Trade Name, for example 'My COMPANY' and for Business name 'DE: JUAN PEREZ'")

    # Extendemos la funcion WRITE o UPDATE
    # @api.multi
    # def write(self, vals):
    #     """
    #     Extendemos para que se pueda guardar sin datos o con los valores por default cuando es regimen simplificado.
    #     Ya q desde pantalla al seleccionar regimen simplificado ya quitamos el attr de required para algunos campos.
    #
    #     Ejemplo de vals, si estarian en blanco desde pantalla:
    #     # tomar en cuenta q puede o no tener el KEY: u'bol_is_rts': True
    #     {u'bol_invoice_date_limit': False, u'bol_invoice_gasoline_percentage': False, u'bol_invoice_proportion_key': False,
    #     u'bol_invoice_auth_nro': False, u'bol_invoice_category': False}
    #     """
    #
    #     # declaramos una variable para controlar si permitimos colocar valores vacios por se regimen simplificado o no.
    #     boolCanEmpty = False
    #     # Primero verificamos si vals tiene el KEY bol_is_rts y si es para colocar el valor TRUE
    #     if 'bol_is_rts' in vals:
    #         # Tomar en cuenta que bol_is_rts puede estar en el diccionario para cambiar de regimen general a simplificado y/o viceversa
    #         # por tanto solamente se toma en cuenta si el valor esta en TRUE
    #         # caso contrario boolCanEmpty sigue en false y tampoco entra el el elif de abajo.
    #         if vals['bol_is_rts'] is True:
    #             boolCanEmpty = True
    #             # Si esta establecido el regimen Simplificado, entonces no puede ser regimen tasa CERO q es un regimen especial
    #             # asi q lo establecemos en FALSE por mas haya sido o no especificado en diccionario vals.
    #             vals['bol_is_rtc'] = False
    #     # Ahora verificamos : puede ser que la company ya este establecida como regimen tributario simplificado
    #     # y se quiera actualizar valores, por tanto solo veificamos el valor de self.bol_is_rts
    #     elif self.bol_is_rts:
    #         boolCanEmpty = True

        # Validamos si podemos agregar items vacios para colocar sus valores por default
        # como Regimen Tributario Simplificado.
        # if boolCanEmpty:
        #     # verificamos ciertos campos para ver si estan en el diccionario como False (nunca vienen como NONE o NULL)
        #     # y colocamos un valor por defecto para evitar un error al intentar guardarlos.
        #     if 'bol_invoice_date_limit' in vals and not vals['bol_invoice_date_limit']:
        #         vals['bol_invoice_date_limit'] = fields.Date.today()
        #     if 'bol_invoice_gasoline_percentage' in vals and not vals['bol_invoice_gasoline_percentage']:
        #         vals['bol_invoice_gasoline_percentage'] = 0
        #     if 'bol_invoice_proportion_key' in vals and not vals['bol_invoice_proportion_key']:
        #         vals['bol_invoice_proportion_key'] = 'rts'
        #     if 'bol_invoice_auth_nro' in vals and not vals['bol_invoice_auth_nro']:
        #         vals['bol_invoice_auth_nro'] = '0000000000'
        #     if 'bol_invoice_category' in vals and not vals['bol_invoice_category']:
        #         vals['bol_invoice_category'] = 'rts'
        #
        # # Ahora ejecutamos la logica de la BASE
        # return super(res_company, self).write(vals)

    # Constraint
    # no se puede adicionar una fecha de emision menor a la fecha actual...

    # @api.one
    # @api.constrains('bol_invoice_date_limit')
    # def _check_invoice_date_limit(self):
    #     # print "K32 bol_invoice_date_limit", self.bol_invoice_date_limit
    #     # print "K32 fields.Date.today()", fields.Date.today()
    #     # print "K32 fields.Date.from_string", fields.Date.from_string(fields.Date.today())
    #     # if fields.Date.from_string(self.bol_invoice_date_limit) < fields.Date.from_string(fields.Date.today()):
    #     # usar Date.context_today en lugar de Date.today para evitar error de fecha timezone del usuario logueado
    #     # es decir, si tenemos la fecha limite de emision 2019-01-23, la fecha del dia es 2019-01-23, pero resulta que si ejecutamos Date.today() nos retorna 2019-01-24, cuando ya estamos en horario de noche, es decir con GMT -4, es a partir de las 8:00 PM ya estamos en time GMT 12:00AM del 24 de enero.
    #     # por mas que ejecutando en el SO, date , nos retorna 2019-01-23 con timezone de Bolivia, asi que context_today usara el TZ del user.env que se tenga, por ende retornara 2019-01-23 en Bolivia.
    #     # Asi solucionamos el BUG en Newtokyo La Paz: en fecha 2019-01-23 en horario Noche.
    #     # TODO: de repente tendrimos que hacer esto en todas partes que usemos fields.Date.today()
    #     if fields.Date.from_string(self.bol_invoice_date_limit) < fields.Date.from_string(fields.Date.context_today(self)):
    #         raise ValidationError(_('Deadline emition must be greater or equal than current date!'))

    # @api.one
    # @api.constrains('bol_invoice_auth_nro')
    # def _check_invoice_auth_number(self):
    #     # Segun el SIN indica un maximo de 15 caracteres pero no indica un minimo
    #     # por tanto validamos si al hacer trim la longitud es menor a 0
    #     if len(self.bol_invoice_auth_nro.strip()) <= 0:
    #         raise ValidationError(_('Authorization Number incorrect!'))
    #     if not self.bol_invoice_auth_nro.isdigit():
    #         raise ValidationError(_('Authorization Number can only contain digits!'))

    # @api.one
    # @api.constrains('bol_invoice_gasoline_percentage')
    # def _check_invoice_gasoline_percentage(self):
    #     """
    #     Valida que el monto del porcentaje introducido en 'bol_gasoline_percentage' no sea menor a 0 ni mayor al 100 %
    #     """
    #     # COmo es field.FLOAT odoo valida que el valor sea numerico, por tanto no es necesario isdigit() xq ademas daría un warning 'float' object has no attribute 'isdigit'
    #     # if not self.bol_invoice_gasoline_percentage.isdigit():
    #     #     raise ValidationError('Gasoline Percentage can only contain digits!')
    #     if self.bol_invoice_gasoline_percentage < 0.00 or self.bol_invoice_gasoline_percentage > 100.00:
    #         raise ValidationError(_('Gasoline Percentage must be between 0.00 and 100.00 %'))

    # Las validaciones de los titulos para RTC (tasa cero)
    # no las marcamos como contrains
    # Solamente son obligatorios el titulo y subtitulo 1, el subtitulo 2 no es obligatorio
    # es para ciertos eventos publicos.
    # def _check_rtc_title(self):
    #     """
    #     Valida que el Título para la factura en régimen tasa cero haya sido establecido antes de emitir una factura
    #     """
    #     if self.bol_is_rtc:
    #         if not self.bol_rtc_title or len(self.bol_rtc_title.strip()) == 0:
    #             raise ValidationError(_('RTC Title must be set'))

    # def _check_rtc_subtitle(self):
    #     """
    #     Valida que el SubTítulo para la factura en régimen tasa cero haya sido establecido antes de emitir una factura
    #     """
    #     if self.bol_is_rtc:
    #         if not self.bol_rtc_subtitle1 or len(self.bol_rtc_subtitle1.strip()) == 0:
    #             raise ValidationError(_('RTC SubTitle must be set'))

    # funciones para generar las facturas
    # @api.one
    # def check_data_for_emit_invoice(self):
    #     """
    #     Verifica si los datos que se configuracion a la company sirven para emitir facturas.
    #     """
    #     if len(self.bol_invoice_proportion_key) <= 0:
    #         raise ValidationError(_('You must specify the proportion key first under Company Settings.'))
    #
    #     # mandar a validar la fecha limite de emision
    #     self._check_invoice_date_limit()
    #
    #     # validar el nro. de autorizacion
    #     self._check_invoice_auth_number()
    #
    #     # Si esta configurado bajo RTC (tasa CERO), se debe verificar que se tenga establecido los titulos y subtitulos.
    #     if self.bol_is_rtc:
    #         self._check_rtc_title()
    #         self._check_rtc_subtitle()
    #
    #     return True

    # @api.one
    # def get_control_code(self, strTransactionDate, dblAmount, strAuthNumber, strInvoiceNumber, strNIT):
    #     """
    #     Función para generar el código de control según la Norma del SIN, utilizando como llave de dosificación el valor que se tiene en self.bol_invoice_proportion_key
    #     """
    #     return self.get_control_code_with_key(strTransactionDate, dblAmount, strAuthNumber, strInvoiceNumber, strNIT, self.bol_invoice_proportion_key)

    # def get_control_code_with_key(self, strTransactionDate, dblAmount, strAuthNumber, strInvoiceNumber, strNIT, strProportion_key, bolcheckdataforemit=True):
    #     """
    #     Función para generar el código de control según la Norma del SIN, uzando criptografías, dígito verificador y base64 junto a los datos de la factura.
    #     Según el SIN se necesita :
    #     Datos de Dosificación:      - Número de Autorización -> Dato numérico de máximo 15 dígitos.
    #                                 - Número de Factura -> Dato numérico de máximo 12 dígitos.
    #     Datos de la Transacción:    - CI o NIT del cliente -> Dato numérico de máximo 12 dígitos.
    #                                 - Fecha de la Transacción -> Dato numérico de 8 dígitos.
    #                                 - Monto Total de la Transacción -> Sin centavos, redondeados al inmediato superior a partir de los de 50 centavos. (Según Art. 11 de la RA Nro. 05-0048-99)
    #     Llave de Dosificación:      LLave asignadao por el SIN a la dosificación solicitada por el contribuyente. Constituye la llave primaria utilizado por el algortimo de criptografía.
    #
    #     Tomar en cuenta que se valida que se tenga todo bien configurado el model company (datos para impuestos) antes de intentar generar el codigo de control (Por mas que se especifiquen estos en la funcion).
    #
    #     bolcheckdataforemit, Indica si debemos validar o no la configuración de los datos de la company para poder emitir una factura.
    #     Por defecto se hace siempre, pero puede darse el caso (por ejemplo en multidosificacion) que no es necesario que se valide la data de la company ya que se usa una configuracion de una dosificacion en particular.
    #     """
    #     # primero validamos que podamos emitir una factura para poder generar su correspondiente codigo de control
    #     if bolcheckdataforemit:
    #         self.check_data_for_emit_invoice()
    #
    #     # Validamos que la llave de dosificacion especificadad a la funcion no sea un string vacio o null
    #     # Tomar en cuenta que esta llave es la que se indica en la funcion, NO la que se tiene en el model company, es decir este modelo. (self.bol_invoice_proportion_key)
    #     if len(strProportion_key) <= 0:
    #         raise ValidationError(_('You must specify the proportion key.'))
    #
    #     if dblAmount <= 0:
    #         raise ValidationError(_('Amount must be greater than 0!'))
    #
    #     intAmount = self.get_bol_round_amount(dblAmount)
    #
    #     # if request.debug:
    #     #     print "K32 get_control_code_with_key -> intAmount", intAmount
    #
    #     # objTrans = new BOL(strAuthNumber, intInvoiceNumber, intClientNIT, intDate, intTotalAmount, strKEY)
    #     intTransactionDate = self.get_bol_int_date(strTransactionDate)
    #     # if request.debug:
    #     #     print "K32 get_control_code_with_key -> intTransactionDate", intTransactionDate
    #
    #     objTrans = BOL(strAuthNumber, int(strInvoiceNumber), int(strNIT), intTransactionDate, intAmount, strProportion_key)
    #
    #     strControlCode = objTrans.get_control_code()
    #
    #     # if request.debug:
    #     #     print "K32 BOL call", objTrans.get_test()
    #
    #     # Dispose del objeto
    #     del objTrans
    #
    #     # return '00-AA-BB-CC-DD'
    #     # if request.debug:
    #     #     print "K32 get_control_code_with_key -> ", strControlCode
    #
    #     return strControlCode

    def get_bol_round_amount(self, dblAmount):
        """
        Redondea un determinado valor double , quitandole los decimales redondeando al inmediato superior a partir de los 50 centavos.
        Retorna un valor INTEGER
        """

        intAmount = 0

        # Obtenemos la precision que se establece en Odoo.
        # la funcion dp.get_precision usa el 'Name' que se haya puesto para obtener el valor
        # get_precision retorna una tupla de 2 items (16, CantidadDigitos)
        # ver odoo/addons/decimal_precision/decimal_precision.py [54] , [25]
        # declaramos 2 variables, uno es la constante (primer valor) y el otro precision (segundo valor)
        # Al parecer la obtencion usa un mark tools.ormcache y se queda eternamente
        # const, prec = dp.get_precision('Bolivia Invoice Control Code')
        # llamando de la manera tradicional
        prec = self.env['decimal.precision'].search([('name', '=', 'Bolivia Invoice Control Code')], limit=1)
        # if request.debug:
        #     print "K32 prec", prec

        # Puede ser q el usuario haya ido a settings -> data structe -> decimal accurency y haya borrado este item
        # por tanto el valor por defecto seria 0 decimales
        if prec:
            # if request.debug:
            #     print "K32 prec.digits", prec[0].digits
            intAmount = int(round(dblAmount, prec[0].digits))
        else:
            # if request.debug:
            #     print "K32 Se usa por default prec 0"
            intAmount = int(round(dblAmount))

        return intAmount

    def get_bol_int_date(self, strDate):
        """
        Transforma un valor str DATE a su respectivo valor INT, ejeplo 2016-07-31 >> 20160731
        """
        return fields.Date.from_string(strDate).strftime('%Y%m%d')

    # def get_bol_date_limit(self):
    #     """
    #     metodo para devolver la fecha limite de la compañia
    #     :return: fecha limite de dosificacion
    #     """
    #     self.ensure_one()
    #     return self.bol_invoice_date_limit

    # def get_limit_date_state(self):
    #     """
    #     la idea es devolver un campo calculado con los dias faltantes para que termine la fecha limite
    #     de emision de facturas
    #     :return:
    #     -fecha limite
    #     -diferencia de dias respecto a la fecha actual
    #     """
    #     limit_date = self.get_bol_date_limit()
    #     if limit_date:
    #         day_diff = self._get_two_dates_diff(datetime.strptime(limit_date, "%Y-%m-%d"),
    #                                             datetime.strptime(fields.Date.today(), "%Y-%m-%d"))
    #         return {'limit_date': limit_date,
    #                 'date_diff': day_diff}
    #     else:
    #         return False

    def _get_two_dates_diff(self, date_a, date_b):
        """
        metodo para obtener la diferencia de dos fechas en dias
        :param date_a: deberia representar la fecha limite de dosificacion
        :param date_b: deberia representar la fecha actual
        :return:diferecia de las dos fechas en dias
        """
        dif = date_a - date_b
        return dif.days
