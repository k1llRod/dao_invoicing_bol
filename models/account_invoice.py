# -*- coding: utf-8 -*-
import logging
import base64
import ast
import calendar
import re
import requests
import os
import io
import pytz
import xml.etree.ElementTree as ET

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

from odoo.tools import float_is_zero, float_compare
from datetime import datetime, timedelta, date
from odoo import api, fields, models, _
from odoo import exceptions
from odoo.exceptions import ValidationError, UserError


from odoo.addons.siat_sin_bolivia.tools import siat_tools


_logger = logging.getLogger(__name__)

SIAT_STATUS = [('VALIDADA', 'Validada'),
               ('ANULACION CONFIRMADA', 'Anulada')]

SALE_TYPE = [('factura', 'Factura Online'),
             ('manual', 'Factura Manual'),
             ('recibo', 'Recibo')
             ]


class AccountInvoice(models.Model):
    """
    """

    _inherit = 'account.invoice'


    bol_sale_type = fields.Selection(
        [('factura', 'Factura'), ('exportacion', 'Exportación')],
        string='Tipo de Venta'
    )
    # En tu modelo account.invoice
    pos_config_id = fields.Many2one('pos.config', string='Punto de Venta')

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id', 'date_invoice',
                 'type', 'invoice_line_ids.siat_giftcard_ids')
    def _compute_amount(self):
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        self.amount_tax = sum(line.amount for line in self.tax_line_ids)
        self.amount_total = self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id.with_context(date=self.date_invoice)
            amount_total_company_signed = currency_id.compute(self.amount_total, self.company_id.currency_id)
            amount_untaxed_signed = currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign

        # Ahora calculamos y colocamos los valores a las columnas para tener el subtotal y total descuento
        # El subtotal es el valor monto de la suma de precio unidad por cantidad.
        self.siat_bol_sub_total = sum(line.price_unit * line.quantity for line in self.invoice_line_ids)
        # El total descuento, es el valor monto , de todos los descuentos en la factura
        self.siat_bol_total_discount = abs(self.siat_bol_sub_total) - abs(self.amount_total)

    @api.one
    @api.depends('payment_ids')
    def _compute_gift_card(self):
        payments = self.payment_ids.filtered(lambda p: p.journal_id.gift_card)
        monto_gift = sum(x.amount for x in payments) if len(payments) > 0 else 0
        self.siat_monto_gift_card = monto_gift

    @api.model
    def _default_get_bol_sale_type(self):
        # return 'factura'
        # todo: debemos incluir la logica de venta con regimen simplificado
        if self.get_rts():
            return 'recibo'
        else:
            return 'factura'

    siat_invoice_channel = fields.Many2one('siat.cuis',
                                           string='Invoice Channel',
                                           states={'draft': [('readonly', False)]}, copy=False
                                           )
    siat_bol_sale_type = fields.Selection(SALE_TYPE,
                                           string='Sale type',
                                           default=_default_get_bol_sale_type,
                                           help="Seleccion tipo de venta", copy=False)
    siat_bol_nro = fields.Char(string='Invoice number',
                               readonly=True,
                               size=15,
                               help='Invoice Number (Sequence)\n\n'
                               'For Passenger Receipt, is the ticket number (13 Digits without "-")', copy=False)
    # siat_bol_partner_nit = fields.Char('NIT', related='partner_id.nit',
    #                                    size=15,
    #                                    required=True,
    #                                    states={'draft': [('readonly', False)]},
    #                                    copy=False,
    #                                    help='Campo que trae el NIT del partner')
    siat_bol_partner_nit = fields.Char('NIT', size=15,
                                       required=True,
                                       help="Número de Identificación Tributaria que permite identificar " \
                                            "inequívocamente a los contribuyentes y estará compuesto por códigos de control" \
                                            "otorgados por la Administración Tributaria, según el tipo de contribuyente",
                                       default=lambda self: self._get_current_partner_nit())

    siat_bol_partner_cpl = fields.Char('Complemento', related='partner_id.dao_cpl_personal',
                                       size=15,
                                       states={'draft': [('readonly', False)]},
                                       copy=False,
                                       help='Campo que trae el complemento del NIT del partner')

    # Columna con el subtotal (suma del precio * cantidad de todas las lineas de la factura)
    siat_bol_sub_total = fields.Monetary(string='Sub Total (Price * Qty)', store=True, readonly=True,
                                         compute='_compute_amount', copy=False)
    # Columna con el total descuento (Resta de bol_sub_total - amount_total ya q el amount_total tiene
    # el total de precios con discount * cantidad + impuestos de cada linea de la factura.)
    siat_bol_total_discount = fields.Monetary(string='Total Discount', store=True, readonly=True,
                                              compute='_compute_amount', copy=False)
    siat_numero_factura = fields.Integer('Numero Factura')
    siat_cuf = fields.Text('Codigo de autorizacion', help="CUF", copy=False)
    siat_cuis = fields.Char('CUIS', copy=False)
    siat_fecha_emision = fields.Datetime('Fecha Emision', copy=False)
    siat_codigo_metodo_pago = fields.Many2one('tipo.metodo.pago', string='Codigo Metodo de Pago', copy=False)
    siat_monto_total_sujeto_iva = fields.Monetary(string='Monto Total Sujeto Iva', store=True, readonly=True, compute='_compute_amount', copy=False)
    siat_codigo_moneda = fields.Integer('codigo Moneda', copy=False)
    siat_tipo_cambio = fields.Integer('Tipo cambio', copy=False)
    siat_monto_total_moneda = fields.Monetary(string='Monto Total Moneda', store=True, readonly=True, compute='_compute_amount', copy=False)
    siat_monto_gift_card = fields.Monetary(string='Monto Gift Card', store=True, readonly=True, compute='_compute_gift_card', copy=False)
    siat_descuento_adicional = fields.Monetary(string='Descuento Adicional', store=True, readonly=True, compute='_compute_amount', copy=False)
    # siat_codigo_excepcion = fields.Integer('Codigo Excepcion', copy=False)
    siat_codigo_documento_sector = fields.Integer('Codigo Documento Sector', copy=False)
    siat_codigo_emision = fields.Many2one('tipo.emision', string="Codigo emision", copy=False)

    siat_status = fields.Selection(SIAT_STATUS, string='Siat status', copy=False)
    siat_codigo_recepcion = fields.Char(string='Codigo Estado', copy=False)
    siat_codigo_estado = fields.Many2one('mensajes.servicios',string='Codigo Recepcion', copy=False)

    siat_codigo_sucursal = fields.Integer('Codigo Sucursal', copy=False)
    siat_codigo_punto_venta = fields.Integer('Codigo Punto Venta', copy=False)
    siat_cufd = fields.Char('CUFD', copy=False)
    siat_numero_tarjeta = fields.Char('Numero tarjeta', copy=False)

    #todo: generar logica de creacion de picking desde factura de venta, en el caso de que tengamos instalado inventario

    #todo: debemos generar logica para traer el nombre correcto de cliente, tomando en cuenta el tema de nombre comercial

    #todo: debemos tener logica para traer el nit del cliente

    #todo: logica de ejecucion de logica de registro de factura

    #todo: llamar logica de registro de factura cuando se paga un factura

    #todo: llamar logica de registro de factura manualmente en el caso de que deseemos hacerlo antes de registrar un pago

    #todo: aplicar logica de copy=False en los atributos que no queremos que se copien al duplicar, en la logica anterior se extendio el metodo copy()

    # TODO: aplicar logica para setear el qr y mostrar en el invoice, aunque es necesario evaluar ya tal vez no sea necesario realizar esta tarea

    siat_bol_generated = fields.Boolean(string="Bolivia Invoice Generated", readonly=True, default=False, copy=False,
                                        help="It indicates that the invoice has been generated for Bolivia")
    # RMC: Columna calculada imagen QR
    # bol_code_qr contiene la imagen como tal, no se guarda en la BD como BINARY pero si en el DISCO como FileStore.
    siat_bol_code_qr = fields.Binary(string="Code QR",
                                     store=False,
                                     compute="_bol_get_qr_image",
                                     help="QR Code with SIN Bolivia Invoice Info, " \
                                     "size is 200x200px image. " \
                                     "Use this field for print the invoice to the client.", copy=False)

    # bol_qr_data contiene la DATA usada para generar el codigo QR, es decir los datos
    # concatenados y separados por &.
    siat_bol_qr_data = fields.Char(string="Url Invoice", store=True, readonly=True, default='', copy=False)

    siat_xml_file = fields.Binary(string="Code xml", copy=False)

    siat_date_time = fields.Char(string="Siat date time", size=27, copy=False)
    #todo: establecer logica de notificacion de vencimiento de cuf si es necesario

    siat_data_dict = fields.Text(string="Siat Data Dictionary", store=True, readonly=True, copy=False)

    siat_offline = fields.Boolean(string="Fuera de linea", default=False, copy=False)

    siat_evento_significativo_id = fields.Many2one('siat.eventos.significativos', copy=False)

    siat_codigo_excepcion = fields.Boolean(string="Codigo Excepcion", default=False, copy=False)

    # campos para el registro de factura manual
    siat_cafc = fields.Char(string="Cafc", copy=False,
                            help="Esto se encuentra en la factura manual derecha superior")
    siat_fecha_m = fields.Datetime('Fecha Emision', copy=False,
                                   help="Fecha en la que se registro la factura de contingencia")
    siat_num_m = fields.Integer('Numero Factura', copy=False,
                                help="Numero de la factura de contingencia")

    # adicioname el campo client name para que el cambio de nombre del partner no afecte la generacion de los libros de ventas
    # ya que si la venta se hizo a un nombre de clien    te y en el transcurso del tiempo ese cliente cambia de nombre ya sea por error o modificacion
    # la factura en el libro de venta debe generarse con el nombre del partner con el cual se emitio en su momento
    bol_client_name = fields.Char(string='Client name', compute='_get_client_name', store=True,
                                  readonly=1, default=lambda self: self._get_current_partner_name())
    bol_control_code_date = fields.Datetime(string='Date code generation control', readonly=True,
                                            help='Date on which the control code is generated invoice.')
    siat_name_student = fields.Many2one('res.partner', string='Nombre Estudiante', track_visibility='always',
                                        help="Nombre del estudiante por el cual se registra el pago")
    siat_periodo_inv = fields.Char(string='Periodo Facturado', copy=False, default=lambda self: self._get_current_period(),
                                   help="Periodo correspondiente a la mensualidad que se está cancelando")

# LOGICA BASE EXTENDIDA
    # ----------------LOGICA BASE EXTENDIDA--------------------
    # ONCHANGES
    # ----------------LOGICA ONCHANGES--------------------------------

    @api.onchange('siat_bol_sale_type')
    def _onchange_bol_sale_type(self):
        """aplicamos un onchange en el campo 'bol_sale_type' para hacer que cuando cambiemos
        el mismo las lineas de la factura se recalculen los impuestos"""
        if not self.get_rts():
            # todo: es necesario ver que campos debemos reestablecer cuando cambiemos el tipo de factura respecto a SIAT
            # self.bol_nro = ''
            # self.bol_auth_nro = ''
            if self.type in ('out_invoice', 'out_refund'):
                for line in self.invoice_line_ids:
                    line._set_taxes()

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        """
        Extendemos el metodo BASE '_onchange_partner_id', para que a parte de ejecutar la logica de la clase BASE,
        también coloque el NIT de la factura segun el partner_id
        """
        # Usamos una variable result xq hay una extension en warnning->warning.py q usa el resultado de la ejecucion de la BASE
        result = super(AccountInvoice, self)._onchange_partner_id()

        # como llamamos _get_current_partner_nity se necesita esa definicion para usar en default lambda del field,
        # usamos una variable aux para obtener y despues verificar si es un array o un valor entero
        aux_nit = self._get_current_partner_nit()
        # todo: revisar que el partner tiene el mismo campo
        if isinstance(aux_nit, list):
            aux_nit = aux_nit[0]

        self.siat_bol_partner_nit = aux_nit
        #self.bol_nit = aux_nit

        return result

    def get_siat_payment_code(self, code_pago):
        if not code_pago:
            default_pago_id = self.env['ir.values'].get_default('account.config.settings', 'siat_default_payment_code')
            if not default_pago_id:
                raise ValidationError('No esta configurado un metodo de pago por defecto')
            code_pago = self.env['tipo.metodo.pago'].browse(default_pago_id)
            if not code_pago:
                raise ValidationError('No se a encontrado el metodo por defecto del pago')
        return code_pago

    # @api.one
    @api.model
    def get_cufd_data_by_sale_type(self):
        self.ensure_one()
        if self.siat_bol_sale_type != 'manual':
            return self.siat_invoice_channel.cufd_code, self.siat_invoice_channel.control_code
        else:
            #todo: considerar que el cuis, sucursal y punto de venta puede cambiar con el tiempo, se debe evaluar si es correcto para traer el registro deseado
            cufd = self.env['historial.cufd'].get_my_date_cufd(self.siat_invoice_channel.id,
                                                               self.siat_invoice_channel.cuis,
                                                               self.siat_invoice_channel.branch_code,
                                                               self.siat_invoice_channel.selling_point_code,
                                                               self.siat_fecha_emision)
            if not cufd:
                raise ValidationError("No se encontro un CUFD valido.")
            return (cufd.cufd_code, cufd.control_code)

    def set_invoice_siat_data(self, cufd, control_code, code_pago, num_tarjeta, sin_dt=False):
        """ Metodo que establece los parametros que son referentes campos de informacion
            sobre la company en la factura
        """
        # Establece los valores para mostrarlos en la pestaña siat
        dict_data = {
                     'siat_cuis': self.siat_invoice_channel.cuis,
                     'siat_fecha_emision': self.siat_fecha_m if self.siat_fecha_m and self.siat_bol_sale_type == 'manual' else self.date_invoice,
                     'siat_codigo_sucursal': self.siat_invoice_channel.branch_code,
                     'siat_codigo_punto_venta': self.siat_invoice_channel.selling_point_code,
                     'siat_cufd': cufd,
                     'siat_codigo_metodo_pago': code_pago.id,
                     'siat_monto_total_sujeto_iva': self.amount_tax,
                     'siat_codigo_moneda': self.currency_id.siat_codigo_moneda.codigo_clasificador if self.currency_id else self.company_id.currency_id.siat_codigo_moneda.codigo_clasificador,#(metod)si no existe se trae de company Todo adecuar cuando usemos multimoneda
                     'siat_tipo_cambio': self.currency_id.siat_tipo_cambio if self.currency_id else self.company_id.currency_id.siat_tipo_cambio,
                     'siat_monto_total_moneda': self.amount_total, #Todo adecuar cuando usemos multimoneda
                     'siat_numero_tarjeta': num_tarjeta,
                     'siat_numero_factura': self.siat_num_m if self.siat_num_m and self.siat_bol_sale_type == 'manual' else self.siat_numero_factura,
                     'siat_codigo_documento_sector': self.siat_invoice_channel.type_doc_sector.codigo_clasificador,
                     'siat_date_time': str(sin_dt), #TODO: Obtener la fecha del servidor en caso de que sin_dt sea false
                     }
        self.update(dict_data)
        # hace el update de los campos para guardarlos y mostrarlos en el diccionario enviado a siat
        dict_data.update({'siat_cuis': self.siat_invoice_channel.cuis,
                          'siat_cufd_code': control_code,
                          'siat_razon_social_emisor': self.siat_invoice_channel.bol_invoice_category,
                          'siat_municipio': self.siat_invoice_channel.municipality,
                          'siat_codigo_tipo_documento_identidad': self.partner_id.type_doc_identidad.codigo_clasificador,
                          'siat_codigo_sucursal': self.siat_invoice_channel.branch_code,
                          'siat_codigo_punto_venta': self.siat_invoice_channel.selling_point_code,
                          'siat_telefono': self.company_id.phone,
                          'siat_direccion': self.siat_invoice_channel.direction,
                          'siat_nombre_razon_social': self.partner_id.name,  # cliente
                          'siat_nit_emisor': str(self.company_id.siat_nit),
                          'siat_cufd': cufd,
                          'siat_complemento': self.siat_bol_partner_cpl,
                          'siat_leyenda': self.siat_invoice_channel.bol_invoice_caption_2,
                          'siat_numero_documento': self.siat_bol_partner_nit,
                          'siat_codigo_cliente': self.partner_id.cod_cliente_siat if self.partner_id.cod_cliente_siat else self.partner_id.id,
                          'siat_numero_tarjeta': num_tarjeta,
                          'siat_cafc': self.siat_cafc if self.siat_cafc else False, #TODO este campo esta pendiente de ser llenado
                          'siat_usuario': self.env.user.name,
                          'siat_name_student': self.siat_name_student.name if self.siat_name_student else False,
                          'siat_periodo_inv': self.siat_periodo_inv if self.siat_periodo_inv else False,
                          })
        self.update({'siat_data_dict': dict_data})

        for line in self.invoice_line_ids:
            line.set_product_attributes()



    # ----------------LOGICA ONCHANGES--------------------------------

    # API DEPENDES
    # ----------------LOGICA API DEPENDES--------------------

    @api.multi
    @api.depends('partner_id')
    def _get_client_name(self):
        for invoice in self:
            """
            generamos la funcion de obtencion de nombre para llener el campo bol_client_name desde un compute y de esta manera
            al grabar el nombre usado en el momento de generacion de la factura y que este no cambie en documentos futuros
            """
            # todo: revisar que el partner tiene el mismo campo
            if invoice.partner_id.dao_uni_personal_flag:
                invoice.bol_client_name = invoice.partner_id.dao_uni_personal_name
            else:
                invoice.bol_client_name = invoice._get_current_partner_name()

    # @api.one
    # @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id')
    # def _compute_amount(self):
    #     # Calculamos los montos de la BASE
    #     super(AccountInvoice, self)._compute_amount()
    #
    #     # Ahora calculamos y colocamos los valores a las columnas para tener el subtotal y total descuento
    #     # El subtotal es el valor monto de la suma de precio unidad por cantidad.
    #     self.siat_bol_sub_total = sum(line.price_unit * line.quantity for line in self.invoice_line_ids)
    #     # El total descuento, es el valor monto , de todos los descuentos en la factura
    #     self.siat_bol_total_discount = abs(self.siat_bol_sub_total) - abs(self.amount_total)
    #     payments = self.payment_ids.filtered(lambda p: p.journal_id.gift_card)
    #     self.siat_monto_gift_card = sum(x.amount for x in payments)

    # ----------------LOGICA API DEPENDES--------------------

    @api.model
    def get_rts(self):
        # todo: adecuar a la nueva logica sait cuis
        if self.siat_invoice_channel.bol_is_rts:
            return True
        else:
            return False

    def _get_current_partner_name(self):
        """creamos un metodo que nos devuelve un string con el nombre del partner de una factura, en el caso de que
        la factura no tenga uno devolvemos una excepcion"""
        if self:
            self.ensure_one()
            if self.partner_id:
                return self.partner_id.name
            else:
                raise UserError(_("The invoice does not have partner."))

    def _get_current_period(self):

        now = datetime.now()
        month_name = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }[now.month]
        year = now.strftime("%Y")
        period = month_name + " " + year
        return period

    # @api.multi
    # def action_invoice_paid(self):
        """
        Extendemos la BASE para que genere los datos para la factura de Bolivia

        Antes se extendia el metodo confirm_paid donde la BASE lo unico q hacia era:
        def confirm_paid(self):
            return self.write({'state': 'paid'})

        Ahora odoo usa esta funcion action_invoice_paid para colocar como pagada la factura.

        En la BASE se hace validaciones de los estados de las facturas antes de colocar a pagadas.

        Por tanto:
        METODO 1: Generaramos los datos para BOLIVIA solo de las facturas con estado OPEN
        y Después ejecutamos la funcionalidad BASE si pudimos generar las facturas sin problema.
        (En el LOG de la factura se generan 2 cambios de estado de OPEN a PAID)

        METODO 2: Ejecutamos la funcionalidad BASE y después generamos los datos para BOLIVIA de las facturas previamente filtradas.
        (Método Actual, no genera doble estado de OPEN a PAID, solo uno, como tiene q ser.)

        NOTA: existe un tema de LOOP infinito, ya que el que llama a esta función, es desde la BASE en el método
        Extendido _write (accoun_invoice.py[353]), que se ejecuta en cada update o write del model account.invoice.
        por tanto ahora solo se generara si el estado del invoice es open y no se haya ya generado los datos de BOLIVIA.
        Asi evitamos el loop infinito ya que el ._bol_generate_invoice al final hace un self.write para guardar los datos generados.
        """
        # METODO 1
        # # Puede ser q al intentar generar los datos para bolivia de un error
        # # por lo general seria una excepcion, pero de cualquier manera retona un boolean
        # # si es este boolean es TRUE recien ejecutamos el codigo de la BASE
        # # por tanto tendremos una variable para controlar si debemos o no cambiar el estado
        # change_to_paid = True

        # # Primero de todas las facturas de SELF
        # # filtramos solamente las con estado Open
        # # Nos basamo en lo que hace la funcionalidad BASE para obtener que facturas cambiar el estado a PAID.
        # to_generate_bol_data = self.filtered(lambda inv: inv.state == 'open' and not inv.bol_generated)
        # # Generamos los datos para Bolivia, si es que to_generate_bol_data tiene datos
        # if (to_generate_bol_data and len(to_generate_bol_data) > 0):
        #     change_to_paid = to_generate_bol_data._bol_generate_invoice()

        # # EN base a change_to_paid ejecutamos o no la funcionalidad de la BASE
        # if (change_to_paid):
        #     return super(AccountInvoice, self).action_invoice_paid()
        # else:
        #     return False
        # METODO 2
        # Cambiando la Logica, ya que el _bol_generate_invoice al final hace un .write({}) para guardar los datos generados de la factura para BOLIVIA.
        # Ahora primero ejecutamos la funcionalidad BASE
        # para que la BASE ya le ponga estado pagado y no tengamos doble loop o ya el loop infinito que se evito con el filtro and not inv.bol_generated
        # Primero guardamos en variables, todas las facturas a las que debemos generar los datos para Bolivia
        # dejamos el filtro NOT bol_generated xq no sabemos si pueda seguir ocurriendo otro loop infinito..?
        # supuestamente ya no deberia ocurrir, pero no sabemos que otros cambios hay o cosas a tomar en cuenta (acciones, eventos, etc.)
        # POR TANTO AHORA si no se pudo generar datos para la factura, tendran que cancelarla y generar otra nueva.
        # import pudb; pudb.set_trace()

        # to_generate_bol_data = self.filtered(lambda inv: inv.state == 'open' and not inv.bol_generated)
        #
        # # Ejecutamos la BASE
        # res = super(AccountInvoice, self).action_invoice_paid()
        #
        # # Ahora recien generamos los datos Bolivia para la Facturas.
        # if res and len(to_generate_bol_data) > 0:
        #     to_generate_bol_data._bol_generate_invoice()
        #
        # return res

    @api.multi
    def action_invoice_open(self):
        """
        Extendemos la accion de validar una factura cambiando el estado a open
        para que primero valide que no existan duplicados
        :return:
        """
        # Primero validamos que no se duplique la creacion de facturas ya existentes
        self.validate_before_open()

        # Llamamos a la funcionalidad base
        return super(AccountInvoice, self).action_invoice_open()

    #@api.multi
    # def action_force_generate_invoice_bol(self):
    #     """
    #     forzamos la creacion de la factura para cumplir con los requerimiento de cuentas por cobrar,
    #     para ello crearemos la factura sin registrar el pago bajo esta logica haremos que los demas campos
    #     no puedan ser editados en base al campo bol_generated
    #     :return:
    #     """
    #     bool_return = False
    #     sales_type = ["out_invoice", "out_refund"]
    #     if self.type in sales_type:
    #         to_generate_bol_data = self.filtered(
    #             lambda inv: inv.state == 'open' and not inv.bol_generated and inv.bol_sale_type == 'factura')
    #
    #         # Ahora recien generamos los datos Bolivia para la Facturas.
    #         if len(to_generate_bol_data) > 0:
    #             to_generate_bol_data._bol_generate_invoice()
    #             bool_return = True
    #     return bool_return

    # @api.multi
    # def copy(self, default=None):
    #     """
    #     Extender el COPY para que los datos del SIN Bolivia esten vacios.
    #     """
    #     # Solamente ciertos valores lo copiamos con valores vacios o Nulls, xq no se debe copiar el nro de factura por ejemplo ni el codigo de control.
    #     default = dict(default or {}, bol_auth_nro='', bol_date_limit=None, bol_nro='', bol_control_code_date=None,
    #                    bol_control_code_uid=None, bol_control_code=None, bol_generated=False, bol_nit=None,
    #                    bol_qr_data='', bol_is_rts=False, bol_is_rtc=False)
    #     return super(AccountInvoice, self).copy(default=default)

    @api.multi
    def get_taxes_values(self):
        """
        Copia de la CLASE BASE, pero modificando para usar en el precio para el calculo de los TAXES el monto
        afectado por el concepto de gasolina o no.
        """
        tax_grouped = {}
        for line in self.invoice_line_ids:
            # Lo que hacia la clas BASE
            # price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            # Lo q hacemos ahora es llamar a _bol_get_price_gas_for_taxes que no retorna el precio descontando lo no
            # sujeto a credito fiscal, en caso si el producto de la linea es gasolina, pero si no es gasolina retorna
            # el precio normal con descuentos (si tuviese)
            price_unit = line._bol_get_price_gas_for_taxes()
            # if line.discount > 0 and self.type not in ["out_invoice", "out_refund"]:
            if line.discount > 0:
                taxes = line.invoice_line_tax_ids.with_context(round=False).compute_all(price_unit, self.currency_id,
                                                                                        line.quantity, line.product_id,
                                                                                        self.partner_id)['taxes']
            else:
                taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity,
                                                              line.product_id, self.partner_id)['taxes']
            for tax in taxes:
                val = {
                    'invoice_id': self.id,
                    'name': tax['name'],
                    'tax_id': tax['id'],
                    'amount': tax['amount'],
                    'base': tax['base'],
                    'manual': False,
                    'sequence': tax['sequence'],
                    'c': tax['analytic'] and line.account_analytic_id.id or False,
                    'account_id': self.type in ('out_invoice', 'in_invoice') and (
                            tax['account_id'] or line.account_id.id) or (
                                          tax['refund_account_id'] or line.account_id.id),
                }

                # If the taxes generate moves on the same financial account as the invoice line,
                # propagate the analytic account from the invoice line to the tax line.
                # This is necessary in situations were (part of) the taxes cannot be reclaimed,
                # to ensure the tax move is allocated to the proper analytic account.
                if line.account_analytic_id:
                    val['account_analytic_id'] = line.account_analytic_id.id

                key = tax['id']
                if key not in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
        return tax_grouped

    # Metodos propios
    def _get_current_partner_nit(self):
        """
        Obtener el NIT del Partner de la Factura.
        """
        if self.partner_id:
            return self.partner_id.nit
        else:
            return '0'

    def _bol_has_ice_tax(self):
        """
        Retorna un valor booleano que indica si el invoice tiene lineas de impuestos aplicados que sean ICE.
        """
        # En una sola linea seria usando ANY
        return any(tax.tax_id.bol_ice for tax in self.tax_line_ids)

    def _bol_has_gasoline(self):
        """
        Retornar un valor booleano que indica si el invoice tiene linea con productos de tipo GASOLINA.
        """
        # En una sola linea seria usando ANY
        return any(line._bol_has_gasoline() for line in self.invoice_line_ids)

    def _bol_get_ice_amount(self):
        """
        En base a la relacion account_invoice_tax que se tiene en la propiedad account_invoice.tax_line_ids, obtenemos
        la suma de los montos que de impuestos que sean ICE
        """

        self.ensure_one()
        # En una sola linea usando IF not, ROUND y SUM
        # todos los montos de TAXES que sean ICE

        ice_amount = 0.00 if not self._bol_has_ice_tax() else round(
            sum(tax.amount for tax in self.tax_line_ids if tax.tax_id.bol_ice), 2)

        return ice_amount

    def _bol_get_gasoline_amount(self):
        """
        Obtiene el monto total de todos productos que representen 'GASOLINA', con descuentos pero sin impuestos.
        """

        self.ensure_one()
        gas_amount = 0.00 if not self._bol_has_gasoline() else round(
            sum(line.bol_price_subtotal_without_tax for line in self.invoice_line_ids if line._bol_has_gasoline()))

        return gas_amount

    # def _bol_get_importe_base(self, company=False):
    #     """
    #     Obtiene un Diccionario con el Importe BASE y el monto no sujeto a credito Fiscal, asi como los porcentajes aplicados.
    #     Indica también los montos TOTALES con y sin Descuentos e impuestos.
    #
    #     Si no llega el company en la funcion se obtiene el current company
    #     """
    #     self.ensure_one()
    #
    #     # Obtenemos la company si esta no llega en la funcion
    #     if not company:
    #         company = self.env['res.company']._company_default_get('account.invoice')
    #
    #     bolIsRTC = self._get_is_RTC(company)
    #
    #     # Vamos armando el diccionario con las parte basica
    #     # El amount_total tiene el monto con descuentos e impuestos, es decir el monto de la factura como tal.
    #     # El metodo _bol_get_gasoline_amount ya verifica si tiene o no prod. Gasolina
    #     # El metodo _bol_get_ice_amount ya verifica si tiene o no impuestos ICE en alguno de los productos.
    #     dicImporte = {'CompanyNit': company.bol_nit,
    #                   'ImporteTotal': self.bol_sub_total,
    #                   'ImporteBaseOriginal': self.amount_total,
    #                   'ImporteBase': self.amount_total,
    #                   'ImporteUntaxed': self.amount_untaxed,
    #                   'ImporteTax': self.amount_tax,
    #                   'PorcentajeNoSujeto': company.bol_invoice_gasoline_percentage,
    #                   'MontoNoSujeto': 0.00,
    #                   'ImporteGasolina': self._bol_get_gasoline_amount(),
    #                   'TieneGasolina': False,
    #                   'TotalDescuentos': self.bol_total_discount,
    #                   'TieneDescuentos': self.bol_total_discount and self.bol_total_discount > 0,
    #                   'ImporteICE': self._bol_get_ice_amount(),
    #                   'TieneICE': False,
    #                   'EsRTC': bolIsRTC,
    #                   }
    #
    #     # Almacenamos el importe BASE en una variable para despues ir restanto el ICE y el MontoNoSujetoACredito (excento - Gasolina)
    #     floatImporteBase = dicImporte['ImporteBase']
    #
    #     # para calcular el monto no sujeto a credito fiscal,
    #     # se debe verificar si no es TASA CERO, buscar el producto Gasolina o ICE, etc.
    #     # CASO contrario si es TASA CERO todo el monto no es sujeto a credito fiscal.
    #     if not bolIsRTC:
    #
    #         # Verificamos si tiene ICE en BASE al monto, para no volver a evaluar los productos de las lineas de la factura.
    #         if dicImporte['ImporteICE'] > 0.00:
    #             dicImporte['TieneICE'] = True
    #             # AL igual que para la gasolina, se debe reducir el monto del importe ICE al importe BASE
    #             floatImporteBase = floatImporteBase - dicImporte['ImporteICE']
    #
    #         # Ahora el importe BASE puede verse afectado si alguno de los productos q vendemos es gasolina
    #         # se debe aplicar un porcentaje del monto solo de los productos gasolina, valido para credito fiscal, segun configuracion en res_company q es por ley.
    #         # en este momento la ley indica 70% del monto es valido para credito fiscal y el restante 30% no esta sujeto a credito fiscal.
    #         # Para no volver a evaluar los productos de las lineas de la factura, simplemente verificamos si el monto es > 0
    #         if dicImporte['ImporteGasolina'] > 0.00:
    #             floatPorcentajeNoSujeto = dicImporte['PorcentajeNoSujeto']
    #             floatImporteGasolina = dicImporte['ImporteGasolina']
    #
    #             # obtenemos el valor del monto, en base al porcentaje configurado, de lo que no esta sujeto a credito fiscal
    #             floatMontoNoSujeto = floatImporteGasolina * ((floatPorcentajeNoSujeto or 0.0) / 100.0)
    #             # al Importe BASE hay q restarle el monto que no es sujeto a credito fiscal
    #             floatImporteBase = floatImporteBase - floatMontoNoSujeto
    #
    #             # Actualizamos los valores del Diccionario
    #             dicImporte['TieneGasolina'] = True
    #             dicImporte['MontoNoSujeto'] = floatMontoNoSujeto
    #
    #         # AL final actualizamos el valor del monto importe BASE que pudo verse afectado si se tiene ICE O GASOLINA
    #         dicImporte['ImporteBase'] = floatImporteBase
    #     else:
    #         # el Importe de la factura en su totalidad no es sujeto a credito fiscal
    #         dicImporte['ImporteBase'] = 0.00
    #         dicImporte['MontoNoSujeto'] = floatImporteBase
    #         dicImporte['PorcentajeNoSujeto'] = 100.00
    #
    #     # if request.debug:
    #     #     print "K32 _bol_get_importe_base for dicImporte", dicImporte
    #
    #     return dicImporte

    def _get_is_RTC(self, company):
        """
        Obtiene si la COMPANY es Régimen Tasa Cero (RTC), para ver como se obtiene el diccionario _bol_get_importe_base
        Inicialmente se utiliza la configuracion que se tiene en la company especificada.
        Despues se puede extender este método para que sea por sucursales, rubros, o multi-dosificaciones.
        """
        # todo: adecuar el metodo para usar el modelo siat.cuis
        # return company.bol_is_rtc
        return False

    # @api.one
    # def _bol_generate_invoice(self):
    #     """
    #     Generar y guardar los datos necesarios para normativa o legislación de Bolivia.
    #     Nota: No generamos la factura para Bolivia cuando la company esta configurada como regimen simplificado (RTS)
    #           usando nro. factura, Autorización, codigo de control, etc. pero si se la coloca como bol_generated = True y bol_is_rts = True (para seguridad de factura registro)
    #     Nota: No generarmos la factura para Bolivia si el tipo de factura no es por ventas, es decir, si el tipo de factura es compra para la company, por lo tanto la company no debe generar la factura ..!
    #     Nota: Solamente se genera la factura para Bolivia si el monto de esta es mayor a 0 y que el type no sea por refund.
    #     Nota: Si la factura no tiene establecido el date_invoice se coloca el current date.
    #     Nota: si el invoice o factura ya tiene asignado un numero, se reutiliza ese, esto para evitar ir generando numeros y perder la secuencia, ya que una factura se puede hacer refund y volver a estado open y despues de corregir y hacer reconciliacion volver a pagar esta, por tanto en este caso se debe usar el numero ya asignado a la factura.
    #     """
    #     # Nos aseguramos que self sea una sola factura.
    #     self.ensure_one()
    #
    #     # Validamos previamente q la factura solamente sea de VENTAS no de COMPRAS para generar los datos del SIN de BOLIVIA.
    #     # Para ello usamos el domain [["type", "in", ["out_invoice", "out_refund"]]]
    #     # para que para compras el domain es [["type", "in", ["in_invoice", "in_refund"]]]
    #     arrSalesType = ["out_invoice", "out_refund"]
    #     if self.type not in arrSalesType:
    #         # Simplemente retornamos True, no genera datos de Bolivia, no usa el secuencial de nro de factura, ni codigo de control ni QR, simplemente retorna True.
    #         # para que el metodo extendido 'confirm_paid' continue con lo que tiene q hacer
    #         # if request.debug:
    #         #     print "K32 _bol_generate_invoice NO ES UNA VENTA :'(", self.type
    #         # Retornamos True
    #         return True
    #
    #     # Verificamos el monto de la factura.
    #     # el monto self.amount_total es el monto (siempre positivo) de la factura
    #     # el monto self.amount_total_signed es el monto de la factura pero multiplicado *-1 en caso de que la factura este como refund
    #     # se multiplica *-1 si el type del invoice esta en self.type in ['in_refund', 'out_refund'] que es el refund de una compra o refund de una compra
    #     # ver en el nativo el TYPE2REFUND [25]
    #     # if self.amount_total and self.amount_total > 0:
    #     if self.amount_total_signed and self.amount_total_signed > 0:
    #
    #         # Verificamos si la factura tiene la fecha establecida o usamos la fecha actual
    #         strDateInvoice = fields.Date.today() if not self.date_invoice else self.date_invoice
    #
    #         # self.validate_before_bol_generate()
    #
    #         # Obtenemos el company por defecto para el manejo de facturas
    #         company = self.env['res.company']._company_default_get('account.invoice')
    #
    #         # Generamos los datos para la normativa Boliviana.
    #
    #         # NOTA: No generamos la factura para Bolivia cuando la company esta configurada como regimen simplificado (RTS)
    #         # usando la logica de nro. factura, codigo de control , qr, etc.
    #         # pero si guardamos la factura como generada bajo el concepto de regimen simplificado.
    #         # ************************************************
    #         # if company.bol_is_rts:
    #         # reemplazamos el if para que use el metodo _get_is_RTS ya que podremos extenderlo depues si es necesario
    #         if self._get_is_RTS(company) or self.bol_sale_type == 'recibo':
    #             vals = self._get_rts_diccionary(strDateInvoice)
    #         else:
    #             if self.bol_sale_type == 'manual':
    #                 vals = self._get_manual_invoice_diccionary(strDateInvoice, company)
    #             else:
    #                 vals = self._get_emit_diccionary(strDateInvoice, company)
    #
    #         # Guardamos los datos en la BD
    #         self.write(vals)
    #
    #     return True

    def _get_is_RTS(self):
        """
        Obtiene si la CUIS es Régimen Simplificado
        Inicialmente se utiliza la configuracion que se tiene en el cuis especificado.
        Despues se puede extender este método para que sea por sucursales, rubros, o multi-dosificaciones.
        """
        return self.siat_invoice_channel.bol_is_rts

    def _get_rts_diccionary(self, strDateInvoice):
        """
        Obtiene un Diccionario con la información para emitir un COMPROBANTE (Factura) en REGIMEN SIMPLIFICADO
        """
        # Debemos guardar el campo bol_is_rts en TRUE
        # ya la factura como GENERADA para Bolivia
        # Este valor nos permitira imprimir esta factura como RECIBO sin valor de credito fiscal.
        # si es RTS (simplificado) no puede ser RTC (tasa cero)

        dic = {'bol_generated': True,
               'bol_is_rts': True,
               'bol_is_rtc': False,
               'bol_nit': '0',
               'date_invoice': strDateInvoice,
               }

        return dic

    def _get_next_invoice_number(self):
        """ Obtiene el Nro. correlativo del punto de venta específico. """
        if not self.siat_bol_nro:
        # Obtener la secuencia del punto de venta específico
            if self.pos_config_id and self.pos_config_id.sequence_id:
                return self.pos_config_id.sequence_id.next_by_id()
            else:
            # Fallback a secuencia global si no hay secuencia en el POS
                return self.env['ir.sequence'].next_by_code('dao.invoicing.bol.number')
        else:
            return self.siat_bol_nro

    # def _bol_get_DATA_for_QR(self, dicImporte, company, strAuthNumber, invoiceNumber, controlCode, nit):
    #     """
    #     Obtenemos un STRING concatenado separado por PIPES con los valores necesarios para generar un codigo QR para IMPUESTOS.
    #     dicImporte.
    #
    #     Consideraciones del SIN:
    #
    #     - Los montos se deben tratar como STRING con 2 Decimales, y el separador de decimales el '.'
    #     b)La cadena de datos deberá estar separada en cada uno de los campos por el caracter separador vertical de listas “|” (pipe).
    #     c) Cuando algún dato no exista se utilizará en su lugar el caracter cero (0).
    #     - ANEXO N° 18 CONTENIDO DEL CÓDIGO DE RESPUESTA RÁPIDA (CÓDIGO QR) PARA FACTURACIÓN COMPUTARIZADA, OFICINA VIRTUAL, ELECTRÓNICA WEB Y ELECTRÓNICA POR CICLOS
    #     POSICION NOMBRE DEL CAMPO TIPO DE DATO DESCRIPCION OBLIGATORIEDAD LONGITUD MAXIMA
    #     1.  NIT emisor (Número de Identificación Tributaria) Numérico NIT del emisor. SI 12
    #     2.  Número de Factura Numérico Número correlativo de Factura o Nota Fiscal. SI 10
    #     3.  Número de Autorización Numérico Número otorgado por la Administración Tributaria para identificar la dosificación. SI 15
    #     4.  Fecha de emisión Fecha Con formato: DD/MM/AAAA. SI 10
    #     5.  Total Numérico Monto total consignado en la Factura o Nota Fiscal, (utilizando el punto “.” como separador de decimales para los centavos). SI 11
    #     6.  Importe base para el Crédito Fiscal Numérico Monto válido para el cálculo del Crédito Fiscal, (utilizando el punto “.” como separador de decimales para los centavos). SI 11
    #     7.  Código de Control Alfanumérico Código que identifica la transacción comercial realizada con la Factura o Nota Fiscal. SI 17
    #     8.  NIT / CI / CEX Comprador (Número de Identificación Tributaria o Documento de Identidad) Alfanumérico NIT del comprador, en caso de no contar se consignará el número de Cédula de Identidad o Carnet de Extranjería o el carácter cero (0). SI 12
    #     9.  Importe ICE/ IEHD/ TASAS Numérico Monto ICE/IEHD/TASAS, en el caso de no corresponder consignar el carácter cero (0). (Utilizando el punto “.” como separador de decimales para los centavos). CUANDO CORRESPONDA 11
    #     10. Importe por ventas no Gravadas o Gravadas a Tasa Cero Numérico Cuando corresponda, caso contrario se consignará el carácter cero (0). (Utilizando el punto “.” como separador de decimales para los centavos). CUANDO CORRESPONDA 11
    #     11. Importe no Sujeto a Crédito Fiscal Numérico Cuando corresponda, caso contrario se consignará el carácter cero (0). (Utilizando el punto “.” como separador de decimales para los centavos). CUANDO CORRESPONDA 11
    #     12. Descuentos, Bonificaciones y Rebajas Obtenidas Numérico Cuando corresponda, caso contrario se consignará el carácter cero (0). (Utilizando el punto “.” como separador de decimales para los centavos). CUANDO CORRESPONDA 11
    #
    #     :param dicImporte: Diccionario con todo el detalle del importe de la factura.
    #     :type dicImporte: dictionary
    #     :param company: Current Company
    #     :type company: model company
    #     :param strAuthNumber: Numero de Autorizacion
    #     :type strAuthNumber: string
    #     :param invoiceNumber: Nro. Secuencial de la factura.
    #     :type invoiceNumber: string
    #     :param controlCode: Codigo de control de la factura.
    #     :type controlCode: string
    #     :param nit: NIT (cliente) de la factura.
    #     :type nit: string
    #     """
    #     # Para hacer el JOIN todos debe ser strings
    #     # Los montos nos debemos asegurar que sean string con 2 decimales y el separador de decimales el punto '.', sin importar el Language que use el usuario
    #
    #     # el importe total seria el valor total de la factura es decir self.bol_sub_total q es el valor precio unitario por cantidad (sin descuentos ni impuestos)
    #     strImporteTotal = '%.2f' % dicImporte['ImporteTotal']
    #
    #     # El importe BASE seria el total de la factura menos los descuentos, q por definicion seria el valor q se tiene en self.amount_total
    #     # Ahora el importe BASE puede verse afectado si la venta de producto es GASOLINA, ahi se tiene un un porcentaje no sujeto a credito fiscal
    #     strImporteBase = '%.2f' % dicImporte['ImporteBase']
    #
    #     strICE = "0" if not dicImporte['TieneICE'] else '%.2f' % dicImporte['ImporteICE']
    #
    #     # En caso de Ser Regimen TASA CERO el valor de MontoNoSujeto es el total de lo que seria el IMPORTEBASE
    #     # xq este regimen, indica que se emite la factura, pero no es valido para credito fiscal toda la factura.
    #     strNoGravadas = "0" if not dicImporte['EsRTC'] else '%.2f' % dicImporte['MontoNoSujeto']
    #     # No sujetoAcredito FISCAL va cuando es GASOLINA lo que se vende y no es RTC.
    #     strNoSujetoCred = "0" if not dicImporte['TieneGasolina'] else '%.2f' % dicImporte['MontoNoSujeto']
    #     # Descuentos aplicados.
    #     strDiscount = "0" if not dicImporte['TieneDescuentos'] else '%.2f' % dicImporte['TotalDescuentos']
    #
    #     # Concatenamos los datos necesarios separados por |
    #     strData = "|".join([dicImporte['CompanyNit'],
    #                         str(int(invoiceNumber)),
    #                         strAuthNumber,
    #                         fields.Date.from_string(self.date_invoice).strftime('%d/%m/%Y'),
    #                         strImporteTotal,
    #                         strImporteBase,
    #                         controlCode,
    #                         nit,
    #                         strICE,
    #                         strNoGravadas,
    #                         strNoSujetoCred,
    #                         strDiscount]
    #                        )
    #     # if request.debug:
    #     #     print "K32 _get_DATA_for_QR -> strData for QR", strData
    #
    #     # YA NOS ES NECESARIO CODIFICAR el STRDATA
    #     # Codificamos el string para utf-8 para poder usar la funcion barcode
    #     # strData = strData.encode(encoding='UTF-8', errors='strict')
    #     # Debemos transformar el strDATA con urlEncode para que no de error el caracter | (pipe)
    #     # http://dao-odoo9.bo/report/barcode/QR/235732024|1|7904006098968|01/07/2016|80.0|80.0|00-AA-BB-C|0|0|0|0|0
    #     # http://dao-odoo9.bo/report/barcode/QR/235732024%7C1%7C7904006098968%7C01/07/2016%7C80.0%7C80.0%7C00-AA-BB-C%7C0%7C0%7C0%7C0%7C0
    #
    #     # # strData = urllib.urlencode(strData, True)
    #     # strData = quote(strData)
    #     # if request.debug:
    #     #         print "K32 strData(URL encode) for QR", strData
    #
    #     return strData

    # ----------------LOGICA BASE EXTENDIDA--------------------

# LOGICA QR
        # ----------------LOGICA QR--------------------------------
    @api.one
    @api.depends('siat_bol_qr_data')
    def _bol_get_qr_image(self):
        """
        Obtiene la imagen png del QR code con los datos de la factura. tomar en cuenta las consideraciones del SIN:
        a)El tamaño mínimo a ser consignado deberá tener una superficie no menor a 2 cm de alto por 2 cm de ancho.
        Facturación Computarizada: Las Facturas deberán imprimirse en cualquier color de papel distinto al negro.
        El Código QR deberá ser impreso en color negro u otro de tinta oscura sobre fondo que permita la legibilidad.
        """
        # Se debe validar que solamente se genere este QR para la columna compute bol_code_qr, si se tiene generado los valores para BOLIVIA
        # y q la factura no sea para regimen simplificado.
        if self.siat_bol_generated:
            try:
                # llamamos o hacemos lo mismo que hace el controller @route(['/report/barcode' main.py de odoo/report/controller/main.py [54]
                # Si mandamos humanreadable=1 el nivel de correccion de error del QR es L (7%), si mandamos 0 el Nivel es M (15%) que es lo q se necesita para impuestos.
                barcode = self.env['report'].barcode('QR', self.siat_bol_qr_data, width=200, height=200,
                                                     humanreadable=0)
                # if request.debug:
                #     print "K32 barcode", barcode

                # el modelo report en su funcion barcode retorna un image png as string
                # por tanto hay q transformar a un objeto image codificado a base64
                # Como es en memoria usamos un stream
                image_stream = StringIO.StringIO(barcode)
                # colocamos el valor codificandolo a base 64
                self.siat_bol_code_qr = image_stream.getvalue().encode('base64')
                # if request.debug:
                #     print "K32 self.bol_code_qr", self.bol_code_qr
            except (ValueError, AttributeError):
                _logger.error("Cannot compute the QR Code: %s | %s " % (ValueError, AttributeError))
                raise exceptions.Warning(_('Cannot compute the QR Code'))

        return True

    def _bol_get_DATA_for_QR(self, valornit=False, valorcuf=False, valornrofactura=False, valortamano=1):
        """
        Consideraciones del SIN:

        Ruta: Es una ruta o enlace a los servicios de la Administración Tributaria, la ruta definitiva será publicada una vez salga al ambiente de producción.
        valorNit: Es el valor del NIT del emisor de la Factura o Nota de Crédito-Débito.
        valorCuf: Es el Código Único de la Factura de la Factura o Nota de Crédito-Débito.
        valorNroFactura: Es el número correlativo de la Factura o Nota de Crédito-Débito.
        valorTamano: es el tamaño para la pre visualización 1 = rollo, 2 = media hoja, si no se incluye este parámetro su valor por defecto será 1.


        La cadena de URL de datos deberá estar separada en cada uno de los campos por el caracter separador “&”.


        :param Ruta: Ruta o enlace a los servicios de impuestos https://pilotosiat.impuestos.gob.bo/consulta/QR?
        :type ruta: url
        :param valorNit: Es el valor del NIT
        :type valorNit:
        :param valorCuf: Es el Código Único de la Factura
        :type valorCuf:
        :param valorNroFactura: Es el número correlativo de la Factura.
        :type valorNroFactura:
        :param valorTamano: es el tamaño para la pre visualización 1 = rollo, 2 = media hoja, si no se incluye este parámetro su valor por defecto será 1.
        :type valorTamano:
        """
        # Para hacer el JOIN todos debe ser strings

        url_comapany = self.company_id.lnk_st_qr

        # Concatenamos los datos necesarios separados por &
        # https://pilotosiat.impuestos.gob.bo/consulta/QR?nit=valorNit&cuf=valorCuf&numero=valorNroFactura&t=valorTamaño
        # strData = "&".join([url_comapany, valorNit, valorCuf, valorNroFactura, valorTamano])
        self.siat_bol_qr_data = url_comapany + "nit={}&cuf={}&numero={}&t={}".format(valornit, valorcuf, valornrofactura, valortamano)

        # ----------------LOGICA QR--------------------------------

#LOGICA DESCUENTOS
    # ----------------LOGICA DESCUENTOS------------------------
    @api.model
    def invoice_line_move_line_get(self):
        """
        extendemos este metodo para poder adicinar la logica de descuentos sobre facturas tanto de compras y ventas en
        la creacion de sus movimientos contables, para ello sera necesario adicionar dos lineas extras al movimiento y
        editar el monto de la linea principal de transaccion (no la cuenta de 'a cobrar' ni 'por pagar')
        :return:
        res: diccionario con las lineas de la fatura y las lineas de descuento si existe descuento en las lineas de la factura
        """
        # llamamos a la base
        res = super(AccountInvoice, self).invoice_line_move_line_get()
        # si el diccionario tiene informacion y si la factura tiene descuento aplicamos la logica

        if res and self._is_special_bol_discount():
            # este diccionario contendra las lineas de descuento  que se creen en nuestra logica
            discount_lines = []
            # recorremos las lineas de la respuesta generada por la base
            for line in res:
                disc_lines = []
                # buscamos la linea de la factura para obtener informacion como el descuento y otros
                inv_line = self.env['account.invoice.line'].browse(line['invl_id'])
                # preguntamos si la linea tiene descuento
                if inv_line.discount > 0:
                    # si la linea tiene descuento, la linea que se genera por la compra o venta debe tener otro valor
                    # este contendra el 87 % del total de la factura sin descuento mas el 13% del descuento
                    price, total_excluded_sin_descuentos, total_excluded_descuentos, discount_tax_excluded = self._calc_price_with_discount(
                        inv_line)
                    # almacenamos el precio en la linea que sera usada en la creacion del movimiento
                    if price > 0:
                        line['price'] = price
                    else:
                        continue
                    # como en este punto ya sabemos que la linea tiene descuento simplemente creamos un dicionario con estas lineas
                    disc_lines = self._get_discount_lines(inv_line, total_excluded_descuentos, discount_tax_excluded)
                if disc_lines and len(disc_lines) > 0:
                    for line_dic in disc_lines:
                        discount_lines.append(line_dic)
            if discount_lines and len(discount_lines) > 0:
                for line_dic in discount_lines:
                    res.append(line_dic)
        return res

    def _get_invoice_discount_amount(self):
        # el campo bol_total_discount lo usamos en el modulo dao_invoicing_bol en esta extencion de account_invoice
        # asi que modularizamos si tuviesemos que cambiar la logica en compras
        return self.bol_total_discount

    def _get_discount_lines(self, inv_line, total_excluded_descuentos, discount_tax_excluded):
        """creamos 2 diccionarios que perteneceran a las lineas faltantes del decuento en los movimiento
        la primera representara la linea del descuento
        la segunta representara la linea del impuesto sobre el descuento

        """

        taxes = self._get_discount_taxes(inv_line)
        dic = []
        for tax in taxes:
            discount_lines = {
                'type': 'src',
                'name': _('Discount'),
                # 'price_unit': -(inv_line.discount * 0.87),
                'price_unit': -(discount_tax_excluded),
                'quantity': 1,
                # 'price': -(inv_line.discount * 0.87),
                'price': -(discount_tax_excluded),
                'account_id': tax.discount_account_id.id,
                'account_analytic_id': inv_line.account_analytic_id.id,
                'invoice_id': self.id,
            }

            discount_lines_tax = {
                'type': 'tax',
                'name': _('Discount IVA'),
                # 'price_unit': -(inv_line.discount * 0.13),
                'price_unit': -(total_excluded_descuentos),
                'quantity': 1,
                # 'price': -(inv_line.discount * 0.13),
                'price': -(total_excluded_descuentos),
                'account_id': tax.discount_tax_account_id.id,
                'account_analytic_id': inv_line.account_analytic_id.id,
                # 'account_analytic_id': False,
                'invoice_id': self.id,
            }
            dic.append(discount_lines)
            dic.append(discount_lines_tax)

        # retornamos los dos dixccionarios
        return dic

    def _calc_price_with_discount(self, inv_line):

        # de la linea obtengo los impuestos q tiene, solo los que tienen el flag especial de calculo
        taxes = self._get_discount_taxes(inv_line)
        total_excluded_sin_descuentos = 0
        total_excluded_descuentos = 0
        total_exclude_discount = 0
        vals = {}
        if taxes:
            amount_total = self._get_total_invoice_without_discount(inv_line)
            # Primero obtengo el 'total_excluded' del precio * unidad sin tomar en cuenta los descuentos
            # IMPORTANTE!!!!!!! para que el tema de redondeo por defecto de la moneda no afecte nuestro calculo, usamos un
            # flag que usa el metodo "compute_all" para usar el redondeo de la moneda o usar un redondeo fijo de 5 decimales
            # para ello simplemente devemos agregar en el contexto "round=False"
            total_excluded_sin_descuentos = taxes.with_context(round=False).compute_all(price_unit=amount_total,
                                                                                        currency=inv_line.currency_id,
                                                                                        quantity=1,
                                                                                        product=inv_line.product_id,
                                                                                        partner=inv_line.partner_id
                                                                                        )['total_excluded']
            # Ahora, obtenemos el monto que representa el total_excluded pero del monto de descuento
            amount_discount = self._get_line_discount_value(inv_line)
            # en este caso, de la misma manera usamos el redonde fijo que tiene el metodo compute_all de taxes
            array_discount = taxes.with_context(round=False).compute_all(price_unit=amount_discount,
                                                                         currency=inv_line.currency_id,
                                                                         quantity=1,
                                                                         product=inv_line.product_id,
                                                                         partner=inv_line.partner_id
                                                                         )
            total_excluded_descuentos = sum(t['amount'] for t in array_discount['taxes'])
            total_exclude_discount = array_discount['total_excluded']

            vals = {'amount_total': amount_total,
                    'total_excluded_sin_descuentos': total_excluded_sin_descuentos,
                    'amount_discount': amount_discount,
                    'array_discount': array_discount,
                    'total_excluded_descuentos': total_excluded_descuentos,
                    'total_exclude_discount': total_exclude_discount,
                    }
        price = self._calc_price_dao(inv_line, taxes, vals)

        return (price, total_excluded_sin_descuentos, total_excluded_descuentos, total_exclude_discount)

    def _calc_price_dao(self, inv_line, taxes, vals):
        price = vals['total_excluded_sin_descuentos'] + vals['total_excluded_descuentos']
        return price

    def _get_total_invoice_without_discount(self, inv_line):
        # como en las lineas de la factura no se almacena en ningun lado el monto total de sin descuento de linea
        # calculamos este con el precio unitario y la cantidad
        return (inv_line.price_unit * inv_line.quantity)

    def _get_line_discount_value(self, inv_line):
        # obtenemos el valor del descuento a partir del porcentaje de la linea y el total sin descuento de la linea
        return self._get_total_invoice_without_discount(inv_line) * (inv_line.discount / 100)
        # como ya tenemos este valor en la linea simplemente lo usamos, y no volvemos a calcular
        # No podemos usar inv_line.dao_literal_discount, xq eso esta en dao_purchase y solo se establece en un onchage en la vista de invoice de compra.
        # pero sabemos que: self.dao_literal_discount = (self.quantity * self.price_unit) * (self.discount / 100)
        # si bien usamos esta misma funcion tanto para ventas como compras, si quisieramos usar dao_literal_discount, tendria que ser en una extension
        # de _get_line_discount_value en purchase, y preguntando si es factura de compra, usar dao_literal_discount
        # caso contrario usar la BASE
        # return inv_line.dao_literal_discount

    def _get_discount_taxes(self, inv_line):
        taxes = inv_line.invoice_line_tax_ids.filtered(lambda t: t.bol_is_for_discount)
        return taxes

    def _is_special_bol_discount(self):
        self.ensure_one()
        # Recorremos todas las lineas del invoice que tengan impuesto con el flag bol_is_for_discount
        # return any(self.invoice_line_ids.mapped("invoice_line_tax_ids"), lambda t: t.bol_is_for_discount)
        return len(self.invoice_line_ids.filtered(lambda l: l.discount > 0.0).mapped("invoice_line_tax_ids").filtered(lambda t: t.bol_is_for_discount)) > 0

    @api.multi
    def compute_invoice_totals(self, company_currency, invoice_move_lines):
        """
        Reemplazamos la logica NATIVA compute_invoice_totals, basicamente copiamos la funcion y solo adicionamos el IF
        not self._is_special_bol_discount(), es decir solo redondeamos el price si no se usa la logica de DESCUENTOS para BOLIVIA especial
        CASO Contrario hace lo que hace lo nativo.

        La unica manera que pudimos hacer esto, es reemplazando, ya que el multi, el contexto aplicaria para varias invoices, asi que este metodo nativamente este multipo pero en si la logica esta para una sola factura
        por ejemplo el self.date_invoice, etc.

        :param company_currency:
        :param invoice_move_lines:
        :return:
        """
        total = 0
        total_currency = 0
        for line in invoice_move_lines:
            if self.currency_id != company_currency:
                currency = self.currency_id.with_context(date=self.date_invoice or fields.Date.context_today(self))
                if not (line.get('currency_id') and line.get('amount_currency')):
                    line['currency_id'] = currency.id
                    line['amount_currency'] = currency.round(line['price'])
                    line['price'] = currency.compute(line['price'], company_currency)
            else:
                line['currency_id'] = False
                line['amount_currency'] = False
                # validamos que la factura tiene descuento y si las lines, por lo menos una tiene un impuesto
                # configurado para descuentos de bolivia
                if not self._is_special_bol_discount():
                    line['price'] = self.currency_id.round(line['price'])
            if self.type in ('out_invoice', 'in_refund'):
                total += line['price']
                total_currency += line['amount_currency'] or line['price']
                line['price'] = - line['price']
            else:
                total -= line['price']
                total_currency -= line['amount_currency'] or line['price']
        return total, total_currency, invoice_move_lines
    # ----------------LOGICA DESCUENTOS------------------------

#LOGICA VALIDACIONES
    # ----------------RUN VALIDATION-------------------------
    @api.multi
    def validate_before_open(self):
        sales_type = ["out_invoice", "out_refund"]

        for inv in self.filtered(lambda invoice: invoice.type in sales_type):
            inv.validate_siat_data()
            inv.validate_nit()
            # validamos que la factura no tenga duplicados respecto al numero de factura y numero de autorizacion
            # todo: adecuar validacion de duplicidad en base a la nueba logica siat
            inv.validate_duplicate()
            # validamos que no exista una factura menor respecto a su fecha
            # todo: revisar si esta validacion sera necesaria
            # inv.validation_less_date_invoice()
            # validamos que no exista una factura mayor respecto a su fecha
            # todo: revisar si esta validacion sera necesaria
            # inv.validation_greater_date_invoice()
            # agregamos validacion de impuestos para que las lineas de la factura tengan los impuestos
            # correspondientes a la configuracion de la factura
            for line in inv.get_lines_for_validate_taxes():
                # validamos que los impuestos coincidan
                if line.invoice_line_tax_ids != line._get_line_taxes():
                    raise UserError(_("Lines taxes do not correspond to the configuration of the invoice"))
        return True

    @api.one
    def validate_siat_data(self):
        if not self.partner_id.type_doc_identidad:
            raise ValidationError("Cliente no tiene tipo de Documento configurado")
        if not self.partner_id.cod_cliente_siat:
            raise ValidationError("Cliente no tiene Código de Cliente configurado")
        if not self.currency_id.siat_codigo_moneda:
            raise ValidationError("Moneda no tiene configurado Código SIAT")
        if self.amount_total == 0:
            raise ValidationError("""Esta factura no puede ser validad, ya que el total es igual a cero:\n
                                    Algunas causas posibles:\n
                                    - No se registraron Lineas\n
                                    - No se cuenta con cantidades o precios unitarios\n
                                    - Descuentos del 100%
                                  """)

    def validate_nit(self):
        if self.siat_bol_partner_nit == "0":
            raise ValidationError("No puede registrar un NIT '0'")

        max_amount_without_nit = self.env['ir.values'].get_default('account.config.settings',
                                                                   'siat_monto_max_cliente_sm')
        if self.siat_bol_partner_nit in ['99002', '99001']:
            if self.amount_total > max_amount_without_nit:
                raise ValidationError("Para montos mayores a Bs. {} debe registrar un NIT Valido".format(max_amount_without_nit))
        else:
            if len(self.siat_bol_partner_nit) < 6 and self.siat_bol_partner_nit > 12:
                raise ValidationError("El NIT no tiene un formato correcto")

        if self.partner_id.type_doc_identidad.codigo_clasificador == 5 and not self.siat_codigo_excepcion:
            if not self.siat_validate_nit(self.siat_bol_partner_nit, self.siat_invoice_channel):
                raise ValidationError("994 - NIT INEXISTENTE")

    @api.model
    def siat_validate_nit(self, nit, channel):
        try:
            res = self.env["siat.servicio.facturacion.codigos"].verificar_nit(nit, channel)
        except Exception, e:
            res = {'transaccion': False,
                   'mensajesList': [{'codigo': 995, 'descripcion': 'SERVICIO NO DISPONIBLE \n' + str(e)}]}
        return res['transaccion']

    def get_lines_for_validate_taxes(self):
        """creamos un metodo que nos devuelva las lineas de la factura para poder modularizar"""
        return self.invoice_line_ids

    # def validate_before_bol_generate(self):
    #     """
    #     creamos un metodo de validacion de fechas de las facturas, para poder usarlas al momento de generar las datos de la factura
    #     para bolivia, ya que a pesar de tener las validacion al momento de validar una factura, si se validan dos facturas
    #     con fechas diferentes y se genera los datos sin de la mayor primero y luego de la menor el correlativo saldra mal
    #     :return: True
    #     """
    #
    #     sales_type = ["out_invoice", "out_refund"]
    #     # recorremos las facturas
    #     for inv in self:
    #         # validamos que la factura sea de tipo venta
    #         if inv.type in sales_type:
    #             # validamos que la factura no tenga una menor respecto a su fecha
    #             inv.validation_less_date_invoice()
    #             # validamos que la factura no tenga una mayot respecto a su fecha
    #             inv.validation_greater_date_invoice()
    #     return True

    def validate_duplicate(self):
        """
        Validar que no existan facturas con el mismo número de autorización y mismo número de factura en la DB
        cuando se ingresan facturas manuales y en caso que el usuario resetee la numeracion de factura
        """
        # todo esta validacion debe adecuarsa a los nuevos campos del siat
        # if self.run_invoices_validation():
        #     self.ensure_one()
        #
        #     if self.bol_nro and self.bol_auth_nro:
        #         invoice = self.env['account.invoice'].search_count([('bol_nro', '=', self.bol_nro),
        #                                                             ('bol_auth_nro', '=', self.bol_auth_nro),
        #                                                             ('id', '!=', self.id)
        #                                                             ]) or 0
        #         if invoice > 0:
        #             raise UserError(
        #                 _("Ya existe una factura registrada con el mismo número de factura y número de autorización"))
        return True

    def validation_less_date_invoice(self):
        """
        Valida que no se pueda ingresar facturas con fecha menor a la ultima factura ingresada
        """

        # Si el usuario ingreso una fecha y la venta es con factura se realiza la validación de la fecha
        if self.siat_bol_sale_type == 'factura':
            dateinvoice = self.date_invoice if self.date_invoice else fields.Date.today()
            # Trae el numero de autorizacion que usa la compañia
            # Todo: debemos hacer que la comparacion de la ultima factura sea cde su misma dosificacion o en todo caso CUF
            company_active_authorization = True  # self._get_bol_invoice_auth_nro(company)
            # Valida si la fecha ingresada es menor a la de la ultima factura guardada
            validation = self.env['account.invoice'].search_count([('date_invoice', '>', dateinvoice),
                                                                   ]) or 0
            if validation > 0:
                raise UserError(_('No puede ingresar facturas con fecha menor a la ultima ingresada'))
        return True

    def validation_greater_date_invoice(self):
        """
        Valida que no se pueda ingresar facturas con fecha mayor a la ultima factura ingresada
        """
        #verificamos si por configuracion debemos correr la validacion
        if self.siat_bol_sale_type == 'factura' and not (self.env['ir.values'].get_default('account.config.settings', 'dao_date_invoice_future') or True):
            dateinvoice = self.date_invoice if self.date_invoice else fields.Date.today()
            if dateinvoice < fields.Date.today():
                raise UserError(_('No puede ingresar facturas con fecha mayor a la fecha actual'))
        return True
    
    def _validate_params_config(self, company):
        """
        Validar si los datos o parametros configurados en la company para emitir facturas esten correctos y en tiempo (fecha limite de emision)
        Esta funcion nos permitira extender despues en otros módulos de multidosificacion.
        Pero en la logica BASE utiliza la configuración de la COMPANY.
        Ya después el model invoice tendrá un FIELD que si es NULL se usa la Matriz o company o si tiene especificaco el ID del model dosificación a utilizar.
        """
        # Primero verificamos si estan los datos configurados para poder emitir facturas
        # todo: revisar si es necesario adecuar este metodo check_data_for_emit_invoice en company
        # company.check_data_for_emit_invoice()
        res = True

    # ----------------RUN VALIDATION---------------------------

    # ----------------LOGICA NUEVA--------------------

    @api.multi
    def action_force_generate_invoice_bol(self):
        for invoice in self:
            invoice.action_siat_push_invoice(pago_code=False, numerotarjeta=False)

    def get_invoice_data_dict(self):
        return ast.literal_eval(str(self.siat_data_dict)) if self.siat_data_dict else {}

    @api.multi
    def action_siat_push_invoice(self, pago_code, numerotarjeta):
        self.ensure_one()
        self.validate_siat_bol_generated()

        evento_significativo = self.env['eventos.significativos']
        self.bol_control_code_date = fields.Datetime.context_timestamp(self, timestamp=datetime.now())

        # --- 1) Caso RTS / recibo: si no se usa el resto del flujo ---
        if self._get_is_RTS() or self.siat_bol_sale_type == 'recibo':
            strDateInvoice = fields.Date.today() if not self.date_invoice else self.date_invoice
            self._get_rts_diccionary(strDateInvoice)
            return
        # --- 2) Inicializaciones seguras ---
        event_id = evento_significativo.browse(False)
        tipo_emision = self.siat_codigo_emision.browse(False)

        # --- 3) Ventas manuales ---
        if self.siat_bol_sale_type == 'manual':
            self.siat_fecha_emision = self.siat_fecha_m
            self.siat_numero_factura = self.siat_num_m

            if self.partner_id.type_doc_identidad.codigo_clasificador == 5:
                self.update({'siat_codigo_excepcion': True})

            tipo_emision = self.siat_codigo_emision.search(
                [('codigo_clasificador', '=', 2)],
                limit=1
            )
            # event_id queda en False para manual (si es lo que quieres)

            # --- 4) Evento significativo definido  ---
        elif self.siat_invoice_channel.evento_significativo:
            tipo_emision = self.siat_codigo_emision.search(
                [('codigo_clasificador', '=', 2)],
                limit=1
            )
            event_id = self.siat_invoice_channel.evento_significativo_id

        # --- 5) Flujo normal: online / offline según conectividad / SIN ---

        else:
            internet_ok = siat_tools.check_conection_internet()
            tax_system_ok = False

            if internet_ok:
                soap_obj = self.env['siat.servicio.facturacion.computarizada']
                try:
                    tax_response = soap_obj.verificar_comunicacion()
                    tax_system_ok = tax_response.transaccion

                    if tax_system_ok:
                        tipo_emision = self.siat_codigo_emision.search(
                            [('codigo_clasificador', '=', 1)],
                            limit=1
                        )
                        # Procesar eventos pendientes al recuperar conexión
                        self.process_pending_events()
                    else:
                        tipo_emision = self.siat_codigo_emision.search(
                            [('codigo_clasificador', '=', 2)],
                            limit=1
                        )
                        event_id = evento_significativo.search(
                            [('codigo_clasificador', '=', 2)],
                            limit=1
                        )
                except Exception as e:
                    tipo_emision = self.siat_codigo_emision.search(
                        [('codigo_clasificador', '=', 2)],
                        limit=1
                    )
                    event_id = evento_significativo.search(
                        [('codigo_clasificador', '=', 2)],
                        limit=1
                    )
                    _logger.error("Error verificando comunicación: %s", str(e))
            else:
                tipo_emision = self.siat_codigo_emision.search(
                    [('codigo_clasificador', '=', 2)],
                    limit=1
                )
                event_id = evento_significativo.search(
                    [('codigo_clasificador', '=', 1)],
                    limit=1
                )
        # --- 6) Datos básicos SIAT ---

        self.siat_codigo_emision = tipo_emision
        self.siat_numero_factura = self._get_next_invoice_number()
        code_pago = self.get_siat_payment_code(pago_code)

        # Solo obtener nuevo CUFD si es modo en línea
        sin_dt = self.siat_invoice_channel.get_information_fecha_hora()
        if self.siat_bol_sale_type != 'manual' and tipo_emision.codigo_clasificador == 1:
            self.siat_invoice_channel.get_cufd_data(sin_dt, force_cufd=True)

        cufd, control_code = self.get_cufd_data_by_sale_type()
        self.set_invoice_siat_data(
            cufd,
            control_code,
            code_pago=code_pago,
            sin_dt=sin_dt,
            num_tarjeta=numerotarjeta
        )

        for line in self.invoice_line_ids:
            line.set_product_attributes()  # <-- ahora sí se ejecuta

        self.siat_cuf = siat_tools.cuf_generator(
            control_code,
            self.dict_cuf_generator(sin_dt, tipo_emision.codigo_clasificador)
        )

        # dict_siat_data: aquí idealmente usar json, no literal_eval
        dict_siat_data = ast.literal_eval(str(self.siat_data_dict))
        sector = self.siat_invoice_channel.type_doc_sector
        constant = self.siat_invoice_channel.mode_constant

        # --- 7) Generación de XML ---
        if constant == 1:
            if sector.codigo_clasificador == 11:
                siat_dict_xml = self.dict_xml_siat_elece(dict_siat_data, numerotarjeta)
            else:
                siat_dict_xml = self.dict_xml_siat_elec(dict_siat_data, numerotarjeta)

            xml_file = self.generate_file_xml(siat_dict_xml)
            res_xml_file = self.send_web_service(xml_file)
            xml_file_sign = self.find_invoice_sign(res_xml_file)
            self.siat_xml_file = self.get_invoice_sign_xml(xml_file_sign)
        else:
            self.siat_xml_file = self.get_invoice_xml(dict_siat_data, numerotarjeta)

        # --- 8) Envío en línea / offline ---
        if tipo_emision.codigo_clasificador == 1:
            gun_zip = siat_tools.generate_file_gzip(self.siat_xml_file, str(self.number))
            gun_zip_binary = base64.encodestring(gun_zip.getvalue())
            hash_256 = siat_tools.action_generator_hash(self.siat_xml_file, 'hash_256')

            obj = self.env['siat.servicio.facturacion']
            try:
                invoice_siat = obj.recepcion_factura(
                    company_id=self.company_id,
                    archivo=gun_zip_binary,
                    hash_archivo=hash_256,
                    cuis=self.siat_invoice_channel,
                    send_date=self.siat_date_time,
                    code_doc_sector=self.siat_codigo_documento_sector,
                    code_emition=self.siat_codigo_emision.codigo_clasificador,
                    branch_code=self.siat_invoice_channel.branch_code,
                    type_invo_doc=str(self.siat_invoice_channel.type_factura.codigo_clasificador),
                )
                if getattr(invoice_siat, 'transaccion', False):
                    self.register_data_response(invoice_siat)
                else:
                    raise ValidationError("La factura no se generó correctamente: %s" % invoice_siat)
            except Exception as e:
                _logger.error("Error enviando factura: %s", str(e))
                raise
        else:
            self.siat_offline = True
            if event_id:
                self.action_asing_event(event_id)

        # --- 9) QR y correo ---
        self._bol_get_DATA_for_QR(
            valornit=dict_siat_data['siat_nit_emisor'],
            valorcuf=self.siat_cuf,
            valornrofactura=self.siat_numero_factura
        )
        self.siat_bol_generated = True
        self.action_send_email_siat()





    def validate_siat_bol_generated(self):
        if self.siat_bol_generated or self.siat_offline:
            raise ValidationError("No factura ya fue generada para el Servicio de Impuestos Nacionales")

    @api.one
    def auth_siat_codigo_excepcion(self):
        if self.partner_id.type_doc_identidad.codigo_clasificador == 5:
            self.update({'siat_codigo_excepcion': True})
        else:
            raise ValidationError("Solo puede autorizar expeción para clientes con NIT")

    def register_data_response(self, invoice_siat):
        self.siat_codigo_estado = self.env['mensajes.servicios'].search([('codigo_clasificador', '=', int(invoice_siat['codigoEstado']))], limit=1)
        self.siat_codigo_recepcion = str(invoice_siat['codigoRecepcion'])
        self.siat_status = str(invoice_siat['codigoDescripcion'])

    def dict_cuf_generator(self, sin_dt, tipo_emision=1):

        dic = {'nit': str(self.company_id.siat_nit),
               'date_time': siat_tools.format_sin_date_to_cuf(sin_dt),
               'sucursal': str(self.siat_invoice_channel.branch_code),
               'modalidad': str(self.siat_invoice_channel.mode_constant),
               'tipo_emision': tipo_emision,
               'tipo_factura': str(self.siat_invoice_channel.type_factura.codigo_clasificador),
               'tipo_documento_sector': str(self.siat_invoice_channel.type_doc_sector.codigo_clasificador),
               'num_factura': str(self.siat_numero_factura),
               'punto_venta': str(self.siat_invoice_channel.selling_point_code)}
        return dic

    def dict_xml_siat(self, dict_siat_data, numerotarjeta):
        """ RMC: Diccionario a ser utilizado en el metodo de action_generate_file_xml de siat"""
        self._compute_gift_card()
        self._compute_amount()
        
        dynamic_values = self.get_dynamic_values()
        total_recalculado = 0

        for line in self.invoice_line_ids:

            subtotal_neto = line.quantity * line.price_unit
            desc = subtotal_neto * (line.discount / 100) if line.discount else 0
            subtotal_final = subtotal_neto - desc

            # REDONDEO CORRECTO
            subtotal_final_redondeado = float("{:.2f}".format(subtotal_final))

            # ACUMULAMOS EL TOTAL
            total_recalculado += subtotal_final_redondeado
            # Formateamos los totales de cabecera también para evitar errores globales
        monto_total_str = "{:.2f}".format(total_recalculado)
        monto_sujeto_iva_str = "{:.2f}".format(total_recalculado - self.siat_monto_gift_card)

        dic_siat = {'name': 'facturaComputarizadaCompraVenta',
                    'name_xsd': 'facturaComputarizadaCompraVenta.xsd',
                    'cabecera': [{'name': 'nitEmisor', 'value': str(dict_siat_data['siat_nit_emisor'])},
                                 {'name': 'razonSocialEmisor', 'value': self.company_id.name},
                                 {'name': 'municipio', 'value': dict_siat_data['siat_municipio']},
                                 {'name': 'telefono', 'value': dict_siat_data['siat_telefono'] if 'siat_telefono' in dict_siat_data else self.company_id.phone},
                                 {'name': 'numeroFactura', 'value': str(self.siat_numero_factura)},
                                 {'name': 'cuf', 'value': self.siat_cuf},
                                 {'name': 'cufd', 'value': dict_siat_data['siat_cufd']},
                                 {'name': 'codigoSucursal', 'value': str(dict_siat_data['siat_codigo_sucursal'])},
                                 {'name': 'direccion', 'value': dict_siat_data['siat_direccion']},
                                 {'name': 'codigoPuntoVenta',
                                  'value': str(dict_siat_data['siat_codigo_punto_venta']) if 'siat_codigo_punto_venta' in dict_siat_data else None},
                                 {'name': 'fechaEmision', 'value': dict_siat_data['siat_date_time']},
                                 {'name': 'nombreRazonSocial',
                                  'value': dict_siat_data['siat_nombre_razon_social'] if 'siat_nombre_razon_social' in dict_siat_data else None},
                                 {'name': 'codigoTipoDocumentoIdentidad',
                                  'value': str(dict_siat_data['siat_codigo_tipo_documento_identidad'])},
                                 {'name': 'numeroDocumento', 'value': str(dict_siat_data['siat_numero_documento'])},
                                 {'name': 'complemento',
                                  'value': str(dict_siat_data['siat_complemento']) if 'siat_complemento' in dict_siat_data and dict_siat_data['siat_complemento'] else None},
                                 {'name': 'codigoCliente', 'value': dict_siat_data['siat_codigo_cliente']},
                                 {'name': 'codigoMetodoPago', 'value': str(self.siat_codigo_metodo_pago.codigo_clasificador)},
                                 {'name': 'numeroTarjeta',
                                  'value': numerotarjeta if numerotarjeta != False else None},
                                 {'name': 'montoTotal', 'value': monto_total_str}, # CORREGIDO FORMATO
                                 {'name': 'montoTotalSujetoIva', 'value': monto_sujeto_iva_str}, # CORREGIDO FORMATO
                                 {'name': 'codigoMoneda', 'value': str(self.siat_codigo_moneda)},
                                 {'name': 'tipoCambio', 'value': str(self.siat_tipo_cambio)},
                                 {'name': 'montoTotalMoneda', 'value': monto_total_str}, # CORREGIDO FORMATO
                                 {'name': 'montoGiftCard',
                                  'value': "{:.2f}".format(self.siat_monto_gift_card) if self.siat_monto_gift_card else None}, # CORREGIDO FORMATO
                                 {'name': 'descuentoAdicional', 'value': dynamic_values['descuento_adicional']},
                                 {'name': 'codigoExcepcion',
                                  'value': str(int(self.siat_codigo_excepcion)) if self.siat_codigo_excepcion else None},
                                 {'name': 'cafc', 'value': dict_siat_data['siat_cafc'] if dict_siat_data['siat_cafc'] != False else None},
                                 {'name': 'leyenda', 'value': dict_siat_data['siat_leyenda']},
                                 {'name': 'usuario', 'value': dict_siat_data['siat_usuario']},
                                 {'name': 'codigoDocumentoSector', 'value': str(self.siat_codigo_documento_sector)}],
                    'detalle': [],}

        # --- AQUI ESTA LA CORRECCION PRINCIPAL ---
        for line in self.invoice_line_ids:
            # Calculos matemáticos crudos
            subtotal_neto = line.quantity * line.price_unit
            desc = subtotal_neto * (line.discount / 100) if line.discount else 0
            subtotal_final = subtotal_neto - desc if line.quantity and line.price_unit else 0
            
            array_line = [{'name': 'actividadEconomica',
                           'value': str(line.product_id.economic_activity.codigo_caeb) if line.product_id and line.product_id.economic_activity else '1'},
                          {'name': 'codigoProductoSin',
                           'value': str(line.product_id.siat_codigo_producto_sin.codigo_producto) if line.product_id and line.product_id.siat_codigo_producto_sin else '1'},
                          {'name': 'codigoProducto',
                           'value': str(line.product_id.default_code) if line.product_id and line.product_id.default_code else str(line.product_id.id)},
                          {'name': 'descripcion', 'value': line.name if line.name else None},
                          {'name': 'cantidad', 'value': str(line.quantity if line.quantity else 0)}, # Cantidad suele aceptar hasta 5 decimales, str suele estar bien, pero cuidado
                          {'name': 'unidadMedida', 'value': str(
                              line.uom_id.siat_product_uom_id.codigo_clasificador) if line.uom_id else str(
                              line.product_id.uom_id.siat_product_uom_id.codigo_clasificador) if line.product_id and line.product_id.uom_id else None},
                          
                          # --- CORRECCIONES DE DECIMALES ---
                          {'name': 'precioUnitario', 'value': "{:.2f}".format(line.price_unit if line.price_unit else 0)}, 
                          {'name': 'montoDescuento', 'value': "{:.2f}".format(desc)},
                          {'name': 'subTotal', 'value': "{:.2f}".format(subtotal_final)},
                          
                          {'name': 'numeroSerie', 'value': None},
                          {'name': 'numeroImei', 'value': None}]
            dic_siat['detalle'].append(array_line)

        return dic_siat

    def dict_xml_siat_edu(self, dict_siat_data, numerotarjeta):
        """ RMC: Diccionario para sector educativo"""
        self._compute_gift_card()
        self._compute_amount()
        # descuentoAdicional = self.get_descuento_adicional() # str(self.siat_descuento_adicional) if self.siat_descuento_adicional else None
        dynamic_values = self.get_dynamic_values()
        dic_siat = {'name': 'facturaComputarizadaSectorEducativo',
                    'name_xsd': 'facturaComputarizadaSectorEducativo.xsd',
                    'cabecera': [{'name': 'nitEmisor', 'value': str(dict_siat_data['siat_nit_emisor'])},
                                 {'name': 'razonSocialEmisor', 'value': self.company_id.name},
                                 {'name': 'municipio', 'value': dict_siat_data['siat_municipio']},
                                 {'name': 'telefono', 'value': dict_siat_data['siat_telefono'] if 'siat_telefono' in dict_siat_data else self.company_id.phone},
                                 {'name': 'numeroFactura', 'value': str(self.siat_numero_factura)},
                                 {'name': 'cuf', 'value': self.siat_cuf},
                                 {'name': 'cufd', 'value': dict_siat_data['siat_cufd']},
                                 {'name': 'codigoSucursal', 'value': str(dict_siat_data['siat_codigo_sucursal'])},
                                 {'name': 'direccion', 'value': dict_siat_data['siat_direccion']},
                                 {'name': 'codigoPuntoVenta',
                                  'value': str(dict_siat_data['siat_codigo_punto_venta']) if 'siat_codigo_punto_venta' in dict_siat_data else None},
                                 {'name': 'fechaEmision', 'value': dict_siat_data['siat_date_time']},# '2021-10-06T16:03:48.675' # todo completar los siguientes campos para suar la logica de diccionario
                                 {'name': 'nombreRazonSocial',
                                  'value': dict_siat_data['siat_nombre_razon_social'] if 'siat_nombre_razon_social' in dict_siat_data else None},
                                 {'name': 'codigoTipoDocumentoIdentidad',
                                  'value': str(dict_siat_data['siat_codigo_tipo_documento_identidad'])},
                                 {'name': 'numeroDocumento', 'value': str(dict_siat_data['siat_numero_documento'])},
                                 {'name': 'complemento',
                                  'value': str(dict_siat_data['siat_complemento']) if 'siat_complemento' in dict_siat_data and dict_siat_data['siat_complemento'] else None},
                                 {'name': 'codigoCliente', 'value': dict_siat_data['siat_codigo_cliente']},
                                 {'name': 'nombreEstudiante', 'value': dict_siat_data['siat_name_student']},
                                 {'name': 'periodoFacturado', 'value': dict_siat_data['siat_periodo_inv']},
                                 {'name': 'codigoMetodoPago', 'value': str(self.siat_codigo_metodo_pago.codigo_clasificador)},
                                 {'name': 'numeroTarjeta',
                                  'value': numerotarjeta if numerotarjeta != False else None},
                                 {'name': 'montoTotal', 'value': dynamic_values['amount_total']},
                                 {'name': 'montoTotalSujetoIva', 'value': str(self.amount_total - self.siat_monto_gift_card)},
                                 {'name': 'codigoMoneda', 'value': str(self.siat_codigo_moneda)},
                                 {'name': 'tipoCambio', 'value': str(self.siat_tipo_cambio)},
                                 {'name': 'montoTotalMoneda', 'value': dynamic_values['amount_total']}, # str(self.siat_monto_total_moneda)
                                 {'name': 'montoGiftCard',
                                  'value': str(self.siat_monto_gift_card) if self.siat_monto_gift_card else None},
                                 {'name': 'descuentoAdicional', 'value': dynamic_values['descuento_adicional']},
                                 {'name': 'codigoExcepcion',
                                  'value': str(int(self.siat_codigo_excepcion)) if self.siat_codigo_excepcion else None},
                                 {'name': 'cafc', 'value': dict_siat_data['siat_cafc'] if dict_siat_data['siat_cafc'] != False else None},
                                 {'name': 'leyenda', 'value': dict_siat_data['siat_leyenda']},
                                 {'name': 'usuario', 'value': dict_siat_data['siat_usuario']},
                                 {'name': 'codigoDocumentoSector', 'value': str(self.siat_codigo_documento_sector)}],
                    'detalle': [],}
        for line in self.invoice_line_ids:
            # todo: debemois considerar que las lineas de factura pueden no tener producto, asi que para algunos campos por ahora ira como"None"
            # mandar product_id si no existe deafult code
            subtotal_neto = line.quantity * line.price_unit
            desc = subtotal_neto * (line.discount / 100) if line.discount else 0
            array_line = [{'name': 'actividadEconomica',
                           'value': str(line.product_id.economic_activity.codigo_caeb) if line.product_id and line.product_id.economic_activity else '1'},
                          {'name': 'codigoProductoSin',
                           'value': str(line.product_id.siat_codigo_producto_sin.codigo_producto) if line.product_id and line.product_id.siat_codigo_producto_sin else '1'},
                          {'name': 'codigoProducto',
                           'value': str(line.product_id.default_code) if line.product_id and line.product_id.default_code else str(line.product_id.id)},
                          {'name': 'descripcion', 'value': line.name if line.name else None},
                          {'name': 'cantidad', 'value': str(line.quantity if line.quantity else 0)},
                          {'name': 'unidadMedida', 'value': str(
                              line.uom_id.siat_product_uom_id.codigo_clasificador) if line.uom_id else str(
                              line.product_id.uom_id.siat_product_uom_id.codigo_clasificador) if line.product_id and line.product_id.uom_id else None},
                          {'name': 'precioUnitario', 'value': str(line.price_unit if line.price_unit else 0)},
                          {'name': 'montoDescuento', 'value': str(desc)},
                          {'name': 'subTotal', 'value': str(subtotal_neto - desc if line.quantity and line.price_unit else 0)},]
            dic_siat['detalle'].append(array_line)

        return dic_siat

    def get_dynamic_values(self):
        return {'descuento_adicional': None,
                'amount_total': str(self.amount_total)}

    # @api.one
    def get_invoice_xml(self, dict_siat_data, numerotarjeta):
        sector = self.siat_invoice_channel.type_doc_sector
        if sector.codigo_clasificador == 11:
            dic_invoice = self.dict_xml_siat_edu(dict_siat_data, numerotarjeta)
        else:
            dic_invoice = self.dict_xml_siat(dict_siat_data, numerotarjeta)
        file_xsd_siat = self.env['ir.values'].get_default('base.config.settings', 'siat_file_xsd')
        xml_file = siat_tools.action_generate_file_xml(dic_invoice, file_xsd_siat)
        # if not xml_file:
        #     raise ValidationError('La validacion con el archivo XSD a fallado')

        # self.siat_xml_file = xml_file
        return xml_file
        # Como es en memoria usamos un stream
        # image_stream = StringIO.StringIO(xml_file)
        # colocamos el valor codificandolo a base 64
        # self.siat_xml_file = image_stream.getvalue().encode('base64')

    def dict_xml_siat_elec(self, dict_siat_data, numerotarjeta):
        """ RMC: Diccionario a ser utilizado en el metodo de action_generate_file_xml de siat"""
        self._compute_gift_card()
        self._compute_amount()
        # descuentoAdicional = self.get_descuento_adicional() # str(self.siat_descuento_adicional) if self.siat_descuento_adicional else None
        dynamic_values = self.get_dynamic_values()
        dic_siat = {'name': 'facturaElectronicaCompraVenta',
                    'name_xsd': 'facturaElectronicaCompraVenta.xsd',
                    'cabecera': [{'name': 'nitEmisor', 'value': str(dict_siat_data['siat_nit_emisor'])},
                                 {'name': 'razonSocialEmisor', 'value': self.company_id.name},
                                 {'name': 'municipio', 'value': dict_siat_data['siat_municipio']},
                                 {'name': 'telefono', 'value': dict_siat_data['siat_telefono'] if 'siat_telefono' in dict_siat_data else self.company_id.phone},
                                 {'name': 'numeroFactura', 'value': str(self.siat_numero_factura)},
                                 {'name': 'cuf', 'value': self.siat_cuf},
                                 {'name': 'cufd', 'value': dict_siat_data['siat_cufd']},
                                 {'name': 'codigoSucursal', 'value': str(dict_siat_data['siat_codigo_sucursal'])},
                                 {'name': 'direccion', 'value': dict_siat_data['siat_direccion']},
                                 {'name': 'codigoPuntoVenta',
                                  'value': str(dict_siat_data['siat_codigo_punto_venta']) if 'siat_codigo_punto_venta' in dict_siat_data else None},
                                 {'name': 'fechaEmision', 'value': dict_siat_data['siat_date_time']},# '2021-10-06T16:03:48.675' # todo completar los siguientes campos para suar la logica de diccionario
                                 {'name': 'nombreRazonSocial',
                                  'value': dict_siat_data['siat_nombre_razon_social'] if 'siat_nombre_razon_social' in dict_siat_data else None},
                                 {'name': 'codigoTipoDocumentoIdentidad',
                                  'value': str(dict_siat_data['siat_codigo_tipo_documento_identidad'])},
                                 {'name': 'numeroDocumento', 'value': str(dict_siat_data['siat_numero_documento'])},
                                 {'name': 'complemento',
                                  'value': str(dict_siat_data['siat_complemento']) if 'siat_complemento' in dict_siat_data and dict_siat_data['siat_complemento'] else None},
                                 {'name': 'codigoCliente', 'value': dict_siat_data['siat_codigo_cliente']},
                                 {'name': 'codigoMetodoPago', 'value': str(self.siat_codigo_metodo_pago.codigo_clasificador)},
                                 {'name': 'numeroTarjeta',
                                  'value': numerotarjeta if numerotarjeta != False else None},
                                 {'name': 'montoTotal', 'value': dynamic_values['amount_total']},
                                 {'name': 'montoTotalSujetoIva', 'value': str(self.amount_total - self.siat_monto_gift_card)},
                                 {'name': 'codigoMoneda', 'value': str(self.siat_codigo_moneda)},
                                 {'name': 'tipoCambio', 'value': str(self.siat_tipo_cambio)},
                                 {'name': 'montoTotalMoneda', 'value': dynamic_values['amount_total']}, # str(self.siat_monto_total_moneda)
                                 {'name': 'montoGiftCard',
                                  'value': str(self.siat_monto_gift_card) if self.siat_monto_gift_card else None},
                                 {'name': 'descuentoAdicional', 'value': dynamic_values['descuento_adicional']},
                                 {'name': 'codigoExcepcion',
                                  'value': str(int(self.siat_codigo_excepcion)) if self.siat_codigo_excepcion else None},
                                 {'name': 'cafc', 'value': dict_siat_data['siat_cafc'] if dict_siat_data['siat_cafc'] != False else None},
                                 {'name': 'leyenda', 'value': dict_siat_data['siat_leyenda']},
                                 {'name': 'usuario', 'value': dict_siat_data['siat_usuario']},
                                 {'name': 'codigoDocumentoSector', 'value': str(self.siat_codigo_documento_sector)}],
                    'detalle': [],}
        for line in self.invoice_line_ids:
            # todo: debemois considerar que las lineas de factura pueden no tener producto, asi que para algunos campos por ahora ira como"None"
            # mandar product_id si no existe deafult code
            subtotal_neto = line.quantity * line.price_unit
            desc = subtotal_neto * (line.discount / 100) if line.discount else 0
            array_line = [{'name': 'actividadEconomica',
                           'value': str(line.product_id.economic_activity.codigo_caeb) if line.product_id and line.product_id.economic_activity else '1'},
                          {'name': 'codigoProductoSin',
                           'value': str(line.product_id.siat_codigo_producto_sin.codigo_producto) if line.product_id and line.product_id.siat_codigo_producto_sin else '1'},
                          {'name': 'codigoProducto',
                           'value': str(line.product_id.default_code) if line.product_id and line.product_id.default_code else str(line.product_id.id)},
                          {'name': 'descripcion', 'value': line.name if line.name else None},
                          {'name': 'cantidad', 'value': str(line.quantity if line.quantity else 0)},
                          {'name': 'unidadMedida', 'value': str(
                              line.uom_id.siat_product_uom_id.codigo_clasificador) if line.uom_id else str(
                              line.product_id.uom_id.siat_product_uom_id.codigo_clasificador) if line.product_id and line.product_id.uom_id else None},
                          {'name': 'precioUnitario', 'value': str(line.price_unit if line.price_unit else 0)},
                          {'name': 'montoDescuento', 'value': str(desc)},
                          {'name': 'subTotal', 'value': str(subtotal_neto - desc if line.quantity and line.price_unit else 0)},
                          {'name': 'numeroSerie', 'value': None},
                          {'name': 'numeroImei', 'value': None}]
            dic_siat['detalle'].append(array_line)

        return dic_siat

    def dict_xml_siat_elece(self, dict_siat_data, numerotarjeta):
        """ RMC: Diccionario a ser utilizado en el metodo de action_generate_file_xml de siat"""
        self._compute_gift_card()
        self._compute_amount()
        # descuentoAdicional = self.get_descuento_adicional() # str(self.siat_descuento_adicional) if self.siat_descuento_adicional else None
        dynamic_values = self.get_dynamic_values()
        dic_siat = {'name': 'facturaElectronicaSectorEducativo',
                    'name_xsd': 'facturaElectronicaSectorEducativo.xsd',
                    'cabecera': [{'name': 'nitEmisor', 'value': str(dict_siat_data['siat_nit_emisor'])},
                                 {'name': 'razonSocialEmisor', 'value': self.company_id.name},
                                 {'name': 'municipio', 'value': dict_siat_data['siat_municipio']},
                                 {'name': 'telefono', 'value': dict_siat_data['siat_telefono'] if 'siat_telefono' in dict_siat_data else self.company_id.phone},
                                 {'name': 'numeroFactura', 'value': str(self.siat_numero_factura)},
                                 {'name': 'cuf', 'value': self.siat_cuf},
                                 {'name': 'cufd', 'value': dict_siat_data['siat_cufd']},
                                 {'name': 'codigoSucursal', 'value': str(dict_siat_data['siat_codigo_sucursal'])},
                                 {'name': 'direccion', 'value': dict_siat_data['siat_direccion']},
                                 {'name': 'codigoPuntoVenta',
                                  'value': str(dict_siat_data['siat_codigo_punto_venta']) if 'siat_codigo_punto_venta' in dict_siat_data else None},
                                 {'name': 'fechaEmision', 'value': dict_siat_data['siat_date_time']},# '2021-10-06T16:03:48.675' # todo completar los siguientes campos para suar la logica de diccionario
                                 {'name': 'nombreRazonSocial',
                                  'value': dict_siat_data['siat_nombre_razon_social'] if 'siat_nombre_razon_social' in dict_siat_data else None},
                                 {'name': 'codigoTipoDocumentoIdentidad',
                                  'value': str(dict_siat_data['siat_codigo_tipo_documento_identidad'])},
                                 {'name': 'numeroDocumento', 'value': str(dict_siat_data['siat_numero_documento'])},
                                 {'name': 'complemento',
                                  'value': str(dict_siat_data['siat_complemento']) if 'siat_complemento' in dict_siat_data and dict_siat_data['siat_complemento'] else None},
                                 {'name': 'codigoCliente', 'value': dict_siat_data['siat_codigo_cliente']},
                                 {'name': 'nombreEstudiante', 'value': dict_siat_data['siat_name_student']},
                                 {'name': 'periodoFacturado', 'value': dict_siat_data['siat_periodo_inv']},
                                 {'name': 'codigoMetodoPago', 'value': str(self.siat_codigo_metodo_pago.codigo_clasificador)},
                                 {'name': 'numeroTarjeta',
                                  'value': numerotarjeta if numerotarjeta != False else None},
                                 {'name': 'montoTotal', 'value': dynamic_values['amount_total']},
                                 {'name': 'montoTotalSujetoIva', 'value': str(self.amount_total - self.siat_monto_gift_card)},
                                 {'name': 'codigoMoneda', 'value': str(self.siat_codigo_moneda)},
                                 {'name': 'tipoCambio', 'value': str(self.siat_tipo_cambio)},
                                 {'name': 'montoTotalMoneda', 'value': dynamic_values['amount_total']},
                                 {'name': 'montoGiftCard',
                                  'value': str(self.siat_monto_gift_card) if self.siat_monto_gift_card else None},
                                 {'name': 'descuentoAdicional', 'value': dynamic_values['descuento_adicional']},
                                 {'name': 'codigoExcepcion',
                                  'value': str(int(self.siat_codigo_excepcion)) if self.siat_codigo_excepcion else None},
                                 {'name': 'cafc', 'value': dict_siat_data['siat_cafc'] if dict_siat_data['siat_cafc'] != False else None},
                                 {'name': 'leyenda', 'value': dict_siat_data['siat_leyenda']},
                                 {'name': 'usuario', 'value': dict_siat_data['siat_usuario']},
                                 {'name': 'codigoDocumentoSector', 'value': str(self.siat_codigo_documento_sector)}],
                    'detalle': [],}
        for line in self.invoice_line_ids:
            # todo: debemois considerar que las lineas de factura pueden no tener producto, asi que para algunos campos por ahora ira como"None"
            # mandar product_id si no existe deafult code
            subtotal_neto = line.quantity * line.price_unit
            desc = subtotal_neto * (line.discount / 100) if line.discount else 0
            array_line = [{'name': 'actividadEconomica',
                           'value': str(line.product_id.economic_activity.codigo_caeb) if line.product_id and line.product_id.economic_activity else '1'},
                          {'name': 'codigoProductoSin',
                           'value': str(line.product_id.siat_codigo_producto_sin.codigo_producto) if line.product_id and line.product_id.siat_codigo_producto_sin else '1'},
                          {'name': 'codigoProducto',
                           'value': str(line.product_id.default_code) if line.product_id and line.product_id.default_code else str(line.product_id.id)},
                          {'name': 'descripcion', 'value': line.name if line.name else None},
                          {'name': 'cantidad', 'value': str(line.quantity if line.quantity else 0)},
                          {'name': 'unidadMedida', 'value': str(
                              line.uom_id.siat_product_uom_id.codigo_clasificador) if line.uom_id else str(
                              line.product_id.uom_id.siat_product_uom_id.codigo_clasificador) if line.product_id and line.product_id.uom_id else None},
                          {'name': 'precioUnitario', 'value': str(line.price_unit if line.price_unit else 0)},
                          {'name': 'montoDescuento', 'value': str(desc)},
                          {'name': 'subTotal', 'value': str(subtotal_neto - desc if line.quantity and line.price_unit else 0)},]
            dic_siat['detalle'].append(array_line)

        return dic_siat

    def generate_file_xml(self, dict_xml):
        NS_XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
        root = ET.Element(dict_xml['name'])
        root.set(NS_XSI + "noNamespaceSchemaLocation", dict_xml['name_xsd'])
        if dict_xml['cabecera']:
            doc = ET.SubElement(root, 'cabecera')
            for line in dict_xml['cabecera']:
                if line['value'] != None:
                    ET.SubElement(doc, line['name']).text = line['value']
                else:
                    ET.SubElement(doc, line['name'], {'xsi:nil': "true"})
        if dict_xml['detalle']:
            for array_line in dict_xml['detalle']:
                doc = ET.SubElement(root, 'detalle')
                for line in array_line:
                    if line['value'] != None:
                        ET.SubElement(doc, line['name']).text = line['value']
                    else:
                        ET.SubElement(doc, line['name'], {'xsi:nil': "true"})
        xml = ET.tostring(root, encoding='UTF-8', method='xml')
        archive_xml = xml.replace("'UTF-8\'", "'UTF-8\' standalone=\'yes\'")
        return archive_xml

    def send_web_service(self, xmlfile):
        # todo seria bueno validar si se tiene la conexion o no
        url = "http://localhost:5000/xml-2-xmldsig"
        siat_pass_cert = self.env['ir.values'].get_default('base.config.settings', 'siat_pass')
        # siat_cetr_adsib = self.env['ir.values'].get_default('base.config.settings', 'siat_cetr')
        ruta_base = self.env['ir.values'].get_default('base.config.settings', 'siat_route')

        payload = xmlfile
        headers = {
            'pass_token': siat_pass_cert,
            'ruta_facturas': ruta_base,
            'Content-Type': 'application/xml'
        }
        # almacenamos la respuesta
        response = requests.request("POST", url, headers=headers, data=payload)
        # obtener la respuesta en formato texto
        filename = response.text
        return str(filename)

    def get_invoice_sign_xml(self, file_sign_xml):

        # file_xml = base64.encodestring(file_sign_xml)
        file_xml = base64.b64encode(file_sign_xml.encode('utf-8'))
        file_xsd = self.env['ir.values'].get_default('base.config.settings', 'siat_file_xsd')
        validation = siat_tools.action_validation_file_xml_xsd(file_xml, file_xsd)
        if validation == False:
            raise UserError('La validacion con el archivo XSD a fallado')
            # return False
        return file_xml

    def process_pending_events(self):
        """Procesar automáticamente todos los eventos pendientes cuando se restaura la conexión"""
        try:
            # Buscar todos los eventos significativos pendientes para este canal
            pending_events = self.env['siat.eventos.significativos'].search([
                ('state', '=', 'draft'),
                ('siat_cuis_id', '=', self.siat_invoice_channel.id),
                ('evento_significativo_id.codigo_clasificador', 'in', [1, 2])  # Incluye ambos tipos de eventos
            ])
            
            _logger.info("Encontrados %d eventos pendientes para procesar", len(pending_events))
            
            for event in pending_events:
                try:
                    # Validar duración máxima del evento (72 horas)
                    start_dt = fields.Datetime.from_string(event.date_start)
                    end_dt = fields.Datetime.from_string(event.date_end)
                    if (end_dt - start_dt) > timedelta(hours=72):
                        _logger.warning("Evento %s excede duración máxima de 72 horas. Saltando.", event.id)
                        continue
                    
                    # Renovar CUFD si es necesario
                    sin_dt = event.siat_cuis_id.get_information_fecha_hora()
                    event.siat_cuis_id.get_cufd_data(sin_dt, force_cufd=True)
                    event.write({'cufd': event.siat_cuis_id.cufd_code})
                    
                    # Registrar evento y paquete de facturas
                    event.action_register_event_significant()
                    event.action_register_package_invoices()
                    
                    # Validar recepción del paquete
                    event.action_inv_package_receipt_validation()
                    
                    _logger.info("Evento %s procesado exitosamente", event.id)
                    
                except Exception as e:
                    _logger.error("Error procesando evento %s: %s", event.id, str(e))
                    # Mantener el evento en estado draft para reintentar más tarde
        
        except Exception as e:
            _logger.error("Error general en process_pending_events: %s", str(e))


    def find_invoice_sign(self, filename):
        # Ruta base para buscar el archivo
        # ruta_base = os.path.expanduser("~/temporal/bkp/facturas/")
        # ruta_base = '/home/daosystems/temporal/bkp/facturas/'
        ruta_base = self.env['ir.values'].get_default('base.config.settings', 'siat_route')

        # Nombre del archivo a buscar
        #fecha_fact = siat_tools.iso_strdt_to_dt_odoo(self.siat_date_time).strftime("%Y-%m-%d-%H-%M-%S")

        # nombre_archivo = "factura_" + str(num_fact) + "_" + fecha_fact + ".xml"
        nombre_archivo = filename
        ruta_completa = os.path.join(ruta_base, nombre_archivo)
        if os.path.exists(ruta_completa):
            # Abre el archivo y lee su contenido
            with io.open(ruta_completa, mode="r", encoding='utf-8-sig') as archivo:
                file_sign = archivo.read()

            return file_sign
        else:
            raise UserError("El archivo "+nombre_archivo+" no se encontró en "+ruta_completa)
    # ----------------LOGICA NUEVA--------------------

#LOGICA CANCELACION
    # ----------------LOGICA CANCELACION-----------------------
    @api.multi
    def action_cancel(self):
        """
        Reemplazamos el metodo BASE para poder distinguir entre usar dao_CANCEL con reversiones y conciliaciones o la logica BASE (que tb la reemplazamos) para eliminar los account.moves.
        Tomar en cuenta que si usamos dao_cancel method,no necesitamos verificar si esta pagada o parcialmente pagada, ya que este metodo rompe conciliacion inicialmente (tenga o no tenga)

        Tomar en cuenta que el boton CANCELAR aparece cuando el estado de la factura esta en Open.

        Por tanto Se tiene que rompe conciliacion con el PAGO, ahi ya el boton cancelar se encargará de hacer este action_cancel.

        SI se hace con el método dao_cancel, al conciliar el mov de la factura con el mov. de reversion, la factura tiene como pagos realizados el mov. reversion conciliado.
        El mov. del PAGO como tal esta POST pero no conciliado, xq se puede usar es pago en otro factura al mismo proveedor o cliente.
        o en su defecto ir a CANCELAR el pago como tal.
        """
        # Primero Verificamos si debemos usar dao_cancel o no.
        dao_cancel = self.get_use_cancel_with_reversal()

        if dao_cancel:
            # Simplemente llamamos a dao_cancel
            self.dao_cancel()
        else:
            self.action_cancel_base()

        return True

    @api.multi
    def dao_cancel(self, groupreconcilebypartner=False):
        """
        Extendemos la función BASE para que a parte de ejecutar la lógica de la BASE,
        Cambie el estado de los INVOICES a CANCELADA

        TOMAR en cuenta que se afecta en FACTURAS de ventas como compras.

        EN POS se extiende el action_cancel para validar si usamos o no estos metodos.

        Para poder usar el concepto CANCELAR - VOLVER A BORRAR - Y Volver a VALIDAR (open invoice),
        es importante RESTABLECER la relación a account.move que existen en el account.invoice.
        Muy Importante: self.write({'move_id': False, 'move_name': False, 'number': False})

        Caso contrario odoo puede complicarse y confundirse entre los movmiento de reversion, como pagos ya realizados y confundir la factura, y marcar como ya pagada al momento de validar el invoice RE-Borrador
        """
        # PRimero ejecutamos la funcionalidad BASE de ROMPER CONCILIACION - CREAR REVERSION - CONCILIAR.
        res = super(AccountInvoice, self).dao_cancel()

        # Establecemos el estado cancelado.
        if res:
            # hay que borrar el move_name y el number tb para que al cambiar a borrar la factura y volver a validarla se genere otro sequence de movimiento
            self.write({'move_id': False, 'move_name': False, 'number': False})
            # cambiamos el estado a cancelado.
            self.set_cancel_state()

        return res

    def get_move_id_for_cancel(self):
        """
        Overridden de la funcion BASE.

        Para poder implementar y ejecutar dao_cancel cada model tiene que saber como obtiene los account.moves_ids
        """
        self.ensure_one()
        # Una factura tiene un move_id, por tanto no necesitamos hacer nigun mapped
        return self.move_id

    @api.multi
    def set_cancel_state(self):
        """
        Establece el ESTADO CANCELADO a la FACTURA.
        """
        self.write(self._get_cancel_dict_state())

    def _get_cancel_dict_state(self):
        """
        Obtiene un diccionario con el KEY de state y el VALUE cancelado.
        """
        return {'state': 'cancel'}

    @api.multi
    def action_cancel_base(self):
        """
        Lógica BASE para cancelar la factura.
        En SI era la logica SOBREESCRITA del action_cancel como tal, basicamente era COPY & Paste pero usando la funcion _get_must_delete_moves (porque puede ser que en otros casos no se tenga que eliminar movimientos contables como es el caso de DAO_POS que existene la funcion indicando FALSE)
        Asi como tb dao_delete_moves
        """
        moves = self.env['account.move']
        # TODO: cambiar la logica para primero preguntar si usamos la logica dao_cancel o la base que es eliminado account.moves.
        for inv in self:
            if inv.move_id and inv._get_must_delete_moves():
                moves += inv.move_id
            if inv.payment_move_line_ids:
                raise UserError(_(
                    'You cannot cancel an invoice which is partially paid. You need to unreconcile related payment entries first.'))

            # ahora coloca un por uno a cada invoice el write de estado y move_ids
            inv.single_action_cancel()

            if moves:
                inv.dao_delete_moves(moves)
        return True

    @api.one
    def single_action_cancel(self):
        self.ensure_one()
        self.write(self._get_delete_value_dictionary())
        return True

    def dao_delete_moves(self, moves):
        # second, invalidate the move(s)
        moves.button_cancel()
        # delete the move this invoice was pointing to
        # Note that the corresponding move_lines and move_reconciles
        # will be automatically deleted too
        moves.unlink()

    def _get_delete_value_dictionary(self):
        """
        Obtiene un diccionario neceario para hacer el write del account.invoice y quitar la relaciones
        que se tiene entre account.invoice y account.move, de manera que despues podamos hacer un unlik de account.moves.
        :return:
        """
        # Obtenemos el diccionario con el KEY de estado y valor cancelado
        dic = self._get_cancel_dict_state()

        # si debemos eliminar los movimientos, adicionamos el KEY move_ID con valor FALSE para que se elimine la relacion.
        if self._get_must_delete_moves():
            dic["move_id"] = False

        return dic

    def _get_must_delete_moves(self):
        """
        Obtiene un valor booleano que indica si debemos o no eliminar los movimientos asociados a la factura en caso de que cancelemos esta.
        :return: bool

        Por defecto, segun la logica nativa se deberia eliminar los account.moves asociadoos.
        Ahora primero verificamos que si tenemos configurado usar la logica DAO CANCEL, no se tiene que eliminar, se deberia usar ajustes de reversion
        DAO: ya despues en otros modulos o contexto se extiende esto para tener una logica distinta.
        """
        use_dao_cancel = self.get_use_cancel_with_reversal()

        if use_dao_cancel:
            return False
        else:
            # Caso contrario se us logica base asi que se eliminaria (ya despues en pos se extiende esta logica para no borrar por mas que no se este usando dao_cancel.)
            return True

    @api.model
    def get_use_cancel_with_reversal(self):
        """
        Verifica si tenemos especificado en la configuracion de settings si usamos la lógica DAO CANCEL, es decir usando REVERSAL y Conciliando, en lugar de la lógica BASE que es la ELIMINACIÓN de movimientos contables.
        dao_paymentcancel = self.env['ir.values'].get_default('account.config.settings', 'dao_payments_cancel')
        """
        return self.env['ir.values'].get_default('account.config.settings', 'dao_payments_cancel')

    # RMC: Boton para realizar cancelacion de facturas en cero y tengan el estado pagada
    def dao_cancel_invoice_cero(self):
        # validamos que self siempre sea un modelo unico y no un array
        self.ensure_one()

        # Se llama a un metodo de la base para realizar la cancelacion
        self.action_cancel()

    @api.one
    @api.depends('payment_ids', 'state')
    def _compute_dao_force_cancel_zero(self):
        if self.state == 'paid' and not self.payment_ids and len(self.payment_ids) == 0:
            self.dao_force_cancel_zero = True
        else:
            self.dao_force_cancel_zero = False

    # ----------------LOGICA CANCELACION-----------------------

#LOGICA STOCK MOVE
    # ----------------LOGICA STOCK MOVE------------------------

    @api.multi
    def get_qty_stock_picking(self):
        """esta funcion obtendra la cantidad de pikings de una factura"""
        for inv in self:
            qty = 0.0
            if inv.state in ('open', 'paid'):
                # Obtenemos la cantidad de stock picking en base al source document que seria el nombre de la factura
                qty = len(self.env['stock.picking'].search([('origin', '=', inv.number)]))

            inv.dao_picking_count = qty

    def _get_picking_transfer(self):
        """
        Esta funcion determina el tipo de movimiento que sera el stock picking, en el caso de una venta
        debe ser una salida de inventario
        """
        type_obj = self.env['stock.picking.type']
        company_id = self.env.context.get('company_id') or self.env.user.company_id.id
        # buscamos y limitamos 1 la busqueda, caso contrario podriamos tener varios (Delivery Orders (ventas backend), PoS Orders (ventas frontend))
        # por defecto deberia retornar el primero (Delivery Orders)
        types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id.company_id', '=', company_id)], limit=1)
        if not types:
            types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id', '=', False)], limit=1)
        # return types[:4]
        return types[0] if types and len(types) > 0 else False

    @api.multi
    def action_stock_transfer(self):
        """funcion para crear un stock piking desde una factura de venta"""
        moves = []
        # obtenemos el picking para ventas
        picking_transfer_id = self._get_picking_transfer()

        for invoice in self:
            # validamos de la factura tengalineas, que sea de tipo open y que no tenga un piking creado
            if not invoice.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if invoice.state != 'open':
                raise UserError(_('Please Validate invoice.'))
            if invoice.dao_picking_count == 0:
                # creamos el diccionario del nuevo piking
                pick = {
                    'picking_type_id': picking_transfer_id.id,
                    'partner_id': invoice.partner_id.id,
                    'origin': invoice.number,
                    'location_dest_id': invoice.partner_id.property_stock_customer.id,
                    'location_id': picking_transfer_id.default_location_src_id.id
                }
                # creamos el piking
                picking = self.env['stock.picking'].create(pick)
                # conseguimos las lineas de la factura y en base a estas creamos las lineas del piking
                # tomar en cuenta que el tipo de producto solamente debemos tomar en cuenta los que son stockeables, es decir el product_type = 'product'
                moves += invoice.invoice_line_ids.filtered(lambda r: r.product_id.type == 'product')._create_stock_moves_transfer(picking)
        # redireccionamos al view de stock.picking con los moves creados.
        return self.action_view_picking()

    @api.multi
    def action_view_picking(self):
        """metodo para mostrar los pikings de una factura, si solo se tiene un piking mostramos directamente el mismo
        y si tiene mas de uno mostramos el tree view"""
        # copiamos la logica de la base de ordenes de compras o ventas
        action = self.env.ref('stock.action_picking_tree_ready')
        result = action.read()[0]
        result.pop('id', None)
        result['context'] = {}
        # result['domain'] = [('id', '=', self.invoice_picking_id.id)]
        result['domain'] = [('id', '=', self.env['stock.picking'].search([('origin', '=', self.number)]).ids)]

        # pick_ids = sum([self.invoice_picking_id.id])
        # filtramos los pikings pertenecientes a la factura
        pick_ids = self.env['stock.picking'].search([('origin', '=', self.number)]).ids
        # si la cantidad de piking se mayor a uno mostramos el listado caso contrario mostramos el piking ya abierto
        if len(pick_ids) > 1:
            result['domain'] = "[('id','in',[" + ','.join(map(str, pick_ids)) + "])]"
        elif len(pick_ids) == 1:
            res = self.env.ref('stock.view_picking_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = pick_ids[0] or False
        return result

    # ----------------LOGICA STOCK MOVE------------------------

#LOGICA NOTIFICACION DOSIFICACIONES
    # ----------------LOGICA NOTIFICACION----------------------
    @api.one
    def _get_notification_status(self):
        """
        este metodo es un compute que devuelve el valor para mostrar un tipo de mensaje respecto
        a la fecha limite de emision de facturas de bolivia, manejamos 4 tipos de mensajes
        :return:
        0: no necesita mensaje (si la fecha limite vence en mas de 5 dias no mostramos ningun mensaje)
        1: la fecha limite esta por vencer
        2: la fecha limite vence hoy
        3: la fecha limite ya vencio
        """
        # iniciamos el estado en cero por defecto (sin notificacion)
        state = '0'
        # traemos la fecha limite de emision y la diferencia
        limit_date_status = self._get_invoice_limit_date_data()
        # validamos que tengamos datos de fecha limite
        if limit_date_status:
            # almacenamos la diferencia
            diff = limit_date_status['date_diff']
            # si la diferencia es mayor a 5 dias no es neceasario hacer nada
            # todo hacer que el valor de 5 dias sea parametirzable desde settings
            if diff < 5 and self.siat_bol_sale_type == 'factura':
                if diff > 0:
                    state = '3'
                elif diff == 0:
                    state = '2'
                else:
                    state = '1'
        self.dao_notify_state = state

    def _get_invoice_limit_date_data(self):
        """
        donde self es la factura, usaremos esta funcion para devolver la fecha limite
        que corresponde a la compañia de la factura, que se asigna en base al contexto del usuario al crearla.
        para poder extender la obtencion de la fecha limite de emision de facturas, separamos la de la funcion
        _get_notification_status y de esta manera los cambios posteriores a esta logica sea mas sencilla
        :return: un diccionario con los datos dela fecha limite y la diferencia de dias respecto a la fecha actual
        """
        self.ensure_one()
        # todo: adecaur el metodo get_limit_date_state para que el modelo siat cuis y no la logica anterior de numero de autorizacion
        # return self.company_id.get_limit_date_state()

        return False
    # ----------------LOGICA NOTIFICACION----------------------
        #
        #     funcion del boton cancelar factura
    def action_invoice_cancel(self):
        self.open_wizard_cancel_invoice_siat()
        res = super(AccountInvoice, self).action_invoice_cancel()
        return res

    def open_wizard_cancel_invoice_siat(self):
    # 1. Manejar casos donde siat_date_time no está establecido
        if not self.siat_date_time or not isinstance(self.siat_date_time, basestring):
        # Usar la fecha de facturación como alternativa
            if not self.date_invoice:
                raise ValidationError('No se puede determinar la fecha de factura. Verifique los campos de fecha.')
        
        # Convertir date_invoice (string) a objeto date
            invoice_date = fields.Date.from_string(self.date_invoice)
            last_day = calendar.monthrange(invoice_date.year, invoice_date.month)[1]
            period_exception = date(invoice_date.year, invoice_date.month, last_day) + timedelta(days=9)
        
            if date.today() > period_exception:
                raise ValidationError('No puede ANULAR una factura pasado el periodo establecido (usando fecha de factura)')
        
            return self._return_wizard()

    # 2. Caso normal con fecha SIAT válida
        try:
            dt_inv = siat_tools.iso_strdt_to_dt_odoo(self.siat_date_time)
            last_day = calendar.monthrange(dt_inv.year, dt_inv.month)[1]
            period_exception = date(dt_inv.year, dt_inv.month, last_day) + timedelta(days=9)
        
            if date.today() > period_exception:
                raise ValidationError('No puede ANULAR una factura pasado el periodo establecido')
    
        except Exception as e:
        # Mensaje compatible con Python 2.7
            error_msg = 'Error procesando fecha SIAT: %s' % str(e)
            raise ValidationError(error_msg)
    
        return self._return_wizard()

    def _return_wizard(self):
        """Función auxiliar para devolver el wizard"""
        return {
        'name': _("Cancelar Factura"),
        'view_mode': 'form',
        'view_type': 'form',
        'target': 'new',
        'views': [(self.env.ref('siat_sin_bolivia.cancel_invoice_siat_form_view').id, 'form')],
        'res_model': 'cancel.invoice.siat',
        'type': 'ir.actions.act_window',
        'context': {'default_invoice_id': self.id}
        }

    @api.multi
    def action_invoice_paid(self):
        to_generate_bol_data = self.filtered(lambda inv: inv.state == 'open' and not inv.siat_bol_generated)
        # Ejecutamos la BASE
        res = super(AccountInvoice, self).action_invoice_paid()
        # Ahora recien generamos los datos Bolivia para la Facturas.
        # if res and len(to_generate_bol_data.filtered(lambda inv: inv.state == 'paid' and not inv.siat_bol_generated)) > 0:
        if res and len(to_generate_bol_data) > 0:
            # if len(to_generate_bol_data.payment_ids) == 1:
            for inv in to_generate_bol_data:
                # todo: debemos cambiar la logica para que se pueda tener mas de 1 metodo de pago, por lo pronto solo se puede emitir un solo pago
                payment_move_ids = inv.payment_move_line_ids
                # journal_ids = inv.payment_move_line_ids.mapped('journal_id').mapped('metodo_pago_id').mapped()
                # if any(journal.metodo_pago_id.codigo_clasificador == 2 for journal in journal_ids):
                nro_tarjeta = False
                for payment_move in payment_move_ids:
                    if payment_move.payment_id.journal_id.metodo_pago_id.codigo_clasificador == 2:
                        nro_tarjeta = payment_move.payment_id.first_number_card + '00000000' + payment_move.payment_id.last_number_card
                payment_code = self.env['siat.payment.codes'].get_payments_code(payment_move_ids.mapped('journal_id'))
                # inv.action_siat_push_invoice(payment_code, nro_tarjeta)
        return res

    def action_validate_invoice_siat(self):
        company = self.company_id
        channel = self.siat_invoice_channel
        if self.siat_codigo_emision.codigo_clasificador == 2:
            return self.env['siat.soap.base'].call_custom_wizard_response('FACTURA ' + self.display_name, 'ESTADO: REGISTRADA ' + self.siat_codigo_emision.descripcion)
        obj = self.env['siat.servicio.facturacion']
        res = obj.verificacion_estado_factura(company_id=company,
                                               code_doc_sector=channel.type_doc_sector.codigo_clasificador,
                                               code_emition=self.siat_codigo_emision.codigo_clasificador,  # TODO:talvez deberiamos de parametrizar
                                               mode_constant=channel.mode_constant,
                                               selling_point_code=channel.selling_point_code,
                                               branch_code=channel.branch_code,
                                               cufd=channel.cufd_code,
                                               cuis=channel.cuis,
                                               type_invo_doc=channel.type_factura.codigo_clasificador,
                                               cuf=self.siat_cuf)
        return self.env['siat.soap.base'].call_custom_wizard_response('Estado '+ str(res['codigoEstado']), str(res['codigoDescripcion']))

    @api.multi
    def action_invoice_sent(self):
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        self.ensure_one()
        template = self.env.ref('dao_invoicing_bol.email_template_edi_invoice_siat', False)
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            default_model='account.invoice',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            mark_invoice_as_sent=True,
            custom_layout="dao_invoicing_bol.email_template_edi_invoice_siat"
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    def action_send_email_siat(self):
        self.ensure_one()
        template = self.env.ref('dao_invoicing_bol.email_template_edi_invoice_siat', False).with_context(lang=self.env.user.lang)
        # compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            model='account.invoice',
            res_id=self.id,
            use_template=bool(template),
            template_id=template and template.id or False,
            composition_mode='comment',
            mark_invoice_as_sent=True,
            custom_layout="account.mail_template_data_notification_email_account_invoice"
        )
        mail_message = self.env['mail.compose.message'].create(ctx)
        mail_message.onchange_template_id_wrapper()
        mail_message.with_context(lang=self.env.user.lang).send_mail()

    def action_send_email_siat_cancel(self):
        self.ensure_one()
        template = self.env.ref('dao_invoicing_bol.email_template_invoice_siat_cancel', False).with_context(
            lang=self.env.user.lang)
        # compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict(
            model='account.invoice',
            res_id=self.id,
            use_template=bool(template),
            template_id=template and template.id or False,
            composition_mode='comment',
            mark_invoice_as_sent=True,
            custom_layout="account.mail_template_data_notification_email_account_invoice"
        )
        mail_message = self.env['mail.compose.message'].create(ctx)
        mail_message.onchange_template_id_wrapper_cancel()
        mail_message.with_context(lang=self.env.user.lang).send_mail()

    def action_send_event(self):
        # date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        #TODO:considerar que debe haber una validacion de valides del fufd dependiendo el tipo de evento
        events = self.env['siat.eventos.significativos'].search([('state', '=', 'draft'),
                                                                 ('siat_cuis_id', '=', self.siat_invoice_channel.id),
                                                                 ('evento_significativo_id.codigo_clasificador', 'in', [1, 2, 3, 4])])
        if events and len(events) > 0:
            for event in events:
                sin_dt = event.siat_cuis_id.get_information_fecha_hora()
                event.siat_cuis_id.get_cufd_data(sin_dt, force_cufd=True)
                event.update({'cufd': event.siat_cuis_id.cufd_code})
                event.action_register_event_significant()
                event.action_register_package_invoices()
        if not events and self.siat_codigo_emision.codigo_clasificador == 2:
            event_id = self.env['eventos.significativos'].search([
                ('codigo_clasificador', '=', 2)
            ], limit=1)
            if event_id:
                self.action_create_event(event_id)

    def action_asing_event(self, event_id):
        """Asignar factura a evento existente o crear uno nuevo"""
        if not event_id:
            return
        
        event = self.env['siat.eventos.significativos'].search([
        ('state', '=', 'draft'),
        ('siat_cuis_id', '=', self.siat_invoice_channel.id),
        ('evento_significativo_id', '=', event_id.id)
        ], limit=1)

    # Convertir el string a datetime real
        now_dt_str = fields.Datetime.now()
        now_dt = datetime.strptime(now_dt_str, "%Y-%m-%d %H:%M:%S")

    # Añadir unos segundos
        end_dt = now_dt + timedelta(seconds=5)

    # Convertir de nuevo a string en formato Odoo
        end_dt_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        if event:
            event.write({
            'date_end': end_dt_str,
            'invoice_ids': [(4, self.id)]
            })
            _logger.info("Factura %s agregada al evento existente ID: %s", self.number, event.id)
        else:
            event = self.env['siat.eventos.significativos'].create({
            'siat_cuis_id': self.siat_invoice_channel.id,
            'company_id': self.company_id.id,
            'evento_significativo_id': event_id.id,
            'descripcion': event_id.descripcion,
            'cuis': self.siat_invoice_channel.cuis,
            'cufd': self.siat_invoice_channel.cufd_code,
            'cufd_event': self.siat_invoice_channel.cufd_code,
            'branch_code': self.siat_invoice_channel.branch_code,
            'selling_point_code': self.siat_invoice_channel.selling_point_code,
            'date_start': now_dt_str,
            'date_end': end_dt_str,  # 👈 diferencia de segundos
            'environment_code': self.company_id.environment_code,
            'siat_nit': str(self.company_id.siat_nit),
            'invoice_ids': [(4, self.id)]
            })
            _logger.info("Nuevo evento creado ID: %s para factura %s", event.id, self.number)
    def action_create_event(self, event_id):
        # event = self.env['eventos.significativos'].search([('codigo_clasificador', '=', 1)], limit=1)

        value = {'siat_cuis_id': self.siat_invoice_channel.id,
                 'company_id': self.company_id.id,
                 'evento_significativo_id': event_id.id,
                 'descripcion': event_id.descripcion,
                 'cuis': self.siat_cuis,
                 'cufd':  self.siat_invoice_channel.cufd_code, #TODO: validar que el CUFD sea el mismo en todas las facturas
                 'cufd_event': self.siat_cufd,
                 'branch_code': self.siat_invoice_channel.branch_code,
                 'selling_point_code': self.siat_invoice_channel.selling_point_code,
                 'date_start': siat_tools.iso_strdt_to_dt_odoo_utc(self.siat_date_time, self.env.user.tz).strftime("%Y-%m-%d %H:%M:%S"),
                 'date_end': siat_tools.iso_strdt_to_dt_odoo_utc(self.siat_date_time, self.env.user.tz).strftime("%Y-%m-%d %H:%M:%S"),
                 'environment_code': self.company_id.environment_code,
                 'siat_nit': str(self.company_id.siat_nit)}
        res = self.env['siat.eventos.significativos'].create(value)
        return res


class AccountInvoiceLine(models.Model):
    """
    """
    _inherit = "account.invoice.line"

    

    siat_actividad_economica = fields.Char("Actividad Economica",
                                      help="Actividad económica registrada en el Padrón Nacional de Contribuyentes relacionada al NIT.")
    siat_codigo_producto_sin = fields.Integer('Codigo Producto Sin',
                                         help="Homologado a los códigos de productos genéricos enviados por el SIN a través del servicio de sincronización.")
    siat_codigo_producto = fields.Char("Codigo Producto",
                                  help="Código que otorga el contribuyente a su servicio o producto.")
    siat_descripcion = fields.Char("Descripcion",
                              help="Descripción que otorga el contribuyente a su servicio o producto.")
    siat_cantidad = fields.Float("cantidad",
                          help="Cantidad del producto o servicio otorgado. En caso de servicio este valor debe ser 1.")
    siat_unidad_medida = fields.Integer("Unidad Medida",
                               help="Valor de la paramétrica que identifica la unidad de medida.")
    siat_numero_serie = fields.Char("Numero Serie",
                              help="Número de serie correspondiente al producto vendido de línea blanca o negra. Nulo en otro caso.")
    # no implementado
    # siat_numero_imei = fields.Char("Numero Imei",
    #                          help="Número de Imei del celular vendido. Nulo en otro caso.")
    siat_is_giftcard = fields.Boolean("Is Giftcard")

    # Columnas
    # se usa la misma funcion _compute_price de la BASE pero la tenemos extendida en esta clase heredada
    bol_price_subtotal_without_tax = fields.Monetary(string='Amount w/o Tax', store=True, readonly=True,
                                                      compute='_compute_price')
    # # Adicionamos columnas para almacenar los campos precio_gas, precio no sujeto
    # # tomar en cuenta que todos son campos compute con la misma funcion '_compute_price'
    bol_price = fields.Float(string='Price With Discount', store=True, readonly=True, compute='_compute_price')
    bol_price_gas = fields.Float(string='Price subject to credit (Gasoline Produc)', store=True, readonly=True,
                                  compute='_compute_price')
    bol_price_no_sujeto = fields.Float(string='Price not subject to credit', store=True, readonly=True,
                                        compute='_compute_price')

    def _bol_has_gasoline(self):
        """
        Retornar un valor booleano que indica si el invoice Line tiene su producto de tipo GASOLINA.
        """
        self.ensure_one()
        # En una sola linea seria usando ANY
        return (self.product_id and self.product_id.bol_is_gas)

    def _bol_get_price(self):
        """
        Obtiene el valor del precio de la linea del invoice o item factura en base a la cantidad, precio por unidad y el descuento del item (si tuviera).
        """
        # Obtenemos el PRECIO, como en la clase BASE, con descuentos si es que tuviera.
        return self.price_unit * (1 - (self.discount or 0.0) / 100.0)

    def _bol_get_price_gas_for_taxes(self):
        """
        Obtiene el valor del precio de la linea del invoice o item factura en base a la cantidad, precio por unidad y el descuento del item.
        Pero se toma en cuenta el porcentaje sujeto a credito fiscal si es que el producto de la linea es gasolina.
        """

        # Primero obtenemos el precio normal, es decir qty por precio aplicando descuentos si es que tiene.
        price = self._bol_get_price()

        # Verificamos si el producto es gasolina y quitamos el porcentaje del precio que no estaria sujeto para credito fiscal.
        if self._bol_has_gasoline():
            # se debe quitar el porcentaje no sujeto a credito fiscal.

            # Obtenemos la company para saber cuanto es el porcentaje no sujeto para credito fiscal por gasolina.
            company = self.env['res.company']._company_default_get('account.invoice')

            floatPorcentajeNoSujeto = company.bol_invoice_gasoline_percentage
            floatMontoNoSujeto = price * ((floatPorcentajeNoSujeto or 0.0) / 100.0)

            # al PRECIO hay q restarle el monto que no es sujeto a credito fiscal
            # Asi ya tenemos el precio para pasar en el calculo de IMPUESTOS del _bol_compute_price_gasoline
            price = price - floatMontoNoSujeto

        return price

    @api.one
    def _compute_price(self):
        """
        Extendemos la funcionalidad de la BASE para que calcule el monto del precio con descuentos pero sin IMPUESTOS
        Si el producto de la linea es GASOLINA se debe calcular con solo el porcentaje del monto sujeto para credito fiscal,
        caso contrario usar la logica de la clase BASE, para ello llamamos la a la funcion _compute_price_gasoline
        """
        # Calculamos el precio de la BASE
        if self._bol_has_gasoline():
            # if request.debug:
            #     print "K32, Logica descontanto el monto no sujeto a credito fiscal para el calculo de impuestos."
            self._bol_compute_price_gasoline()
        else:
            # Llamamos a la logica de la clase BASE
            # if request.debug:
            #     print "K32, Logica Normal de la CLASE BASE"
            super(AccountInvoiceLine, self)._compute_price()

            # Los valores Calculados para precios sujetos y no a credito fiscal
            # self.bol_price = self._bol_get_price()
            # self.bol_price_gas = self._bol_get_price_gas_for_taxes()
            # self.bol_price_no_sujeto = self.bol_price
        # FIN DEL IF

        # Ahora agregamos el calculo de la extension
        # tomamos en cuenta que tanto el IF como ELSE se establece el valor de self.bol_price
        # Ahora si multiplicamos el precio (con descuentos) por la cantidad y lo colocamos en la propiedad (columna) bol_price_subtotal_without_tax
        # self.bol_price_subtotal_without_tax = self.quantity * self.bol_price

    @api.one
    def _bol_compute_price_gasoline(self):
        """
        Copia de la logica de la clase base de la funcion '_compute_price', pero tomando en cuenta la gasolina.
        por tanto el unico cambio es que para el calculo de impuestos, se debe pasar el price para gasolina.
        """

        self.ensure_one()
        if not self._bol_has_gasoline():
            return False

        currency = self.invoice_id and self.invoice_id.currency_id or None
        # El price se lo usa para calcular el .price_subtotal en caso de no tener impuestos.
        price = self._bol_get_price()
        # el price_gas se lo usa para hacer el .compute_all de Taxes.
        price_gas = self._bol_get_price_gas_for_taxes()
        # Obtenemos el monto del precio que no estaria sujeto a credito fiscal.
        price_no_sujeto = price - price_gas
        taxes = False
        if self.invoice_line_tax_ids:
            # ahora para el calculo de impuestos, se debe usar el precio para gasolina.
            taxes = self.invoice_line_tax_ids.compute_all(price_gas, currency, self.quantity, product=self.product_id,
                                                          partner=self.invoice_id.partner_id)

        # if request.debug:
        #     print "K32 price", price
        #     print "K32 price_gas", price_gas
        #     print "K32 price_no_sujeto", price_no_sujeto
        #     print "K32 taxes", taxes

        # Colocamos los valores COMPUTED de presio sujeto y no sujeto para credito fiscal
        # self.bol_price = price
        # self.bol_price_gas = price_gas
        # self.bol_price_no_sujeto = price_no_sujeto

        # Obtenemos el valor para el price_subTotal y el price_subtotal_signed, pero si se aplico impuestos, habria que ver de sumarle el monto de gasolina no sujeto a credito fiscal. q es lo q se quito para el calculo de impuestos.
        self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] + (
                self.quantity * price_no_sujeto) if taxes else self.quantity * price
        if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            price_subtotal_signed = self.invoice_id.currency_id.compute(price_subtotal_signed,
                                                                        self.invoice_id.company_id.currency_id)
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign

    # *******************picking

    def _create_stock_moves_transfer(self, picking):
        """creamos las lineas del piking en base a las lineas de la factura"""
        moves = self.env['stock.move']
        done = self.env['stock.move'].browse()
        for line in self:
            # Tomar en cuenta que price_unit lo calculamos en base a la linea, su uom de la linea y del producto, asi como la factura y company
            # mientras que product_uom_qty es la cantidad puesta como tal en la linea con su respectiva uom.
            template = {'name': line.name or '',
                        'product_id': line.product_id.id,
                        'product_uom': line.uom_id.id,
                        'location_id': picking.picking_type_id.default_location_src_id.id,
                        'location_dest_id': line.invoice_id.partner_id.property_stock_customer.id,
                        'picking_id': picking.id,
                        'move_dest_id': False,
                        'state': 'draft',
                        'company_id': line.invoice_id.company_id.id,
                        'price_unit': line._get_stock_move_price_unit(),
                        'product_uom_qty': line.quantity,
                        'picking_type_id': picking.picking_type_id.id,
                        'procurement_id': False,
                        'account_analytic_id': line.account_analytic_id.id,
                        'route_ids': 1 and [
                            (6, 0,
                             [x.id for x in self.env['stock.location.route'].search([('id', 'in', (2, 3))])])] or [],
                        'warehouse_id': picking.picking_type_id.warehouse_id.id,
                        }
            # creamos el move y lo asocimos a la coleccions de moves done para devolver.
            done += moves.create(template)
        return done

    @api.multi
    def _get_stock_move_price_unit(self):
        """
        Copiamos la misma logica que tiene purchase order line para obtener el precio por unidad
        esto en base al UOM de la linea, del producto y si aplica o no impuestos la linea.
        SOlo que lo agregamos a nivel del movel account.invoice.line
        """
        self.ensure_one()
        # inicializamos las variables a utilizar
        line = self[0]
        invoice = line.invoice_id
        price_unit = line.price_unit
        # verificamos si la linea tiene descuento
        if line.discount:
            price_unit = price_unit - (price_unit * (line.discount / 100))

        # Evaluamos segun impuestos y unidades de medida
        # Primero si tiene impuestos, el precio por unidad es sin impuestos.
        if line.invoice_line_tax_ids:
            price_unit = line.invoice_line_tax_ids.with_context(round=False).compute_all(price_unit,
                                                                                         currency=line.invoice_id.currency_id,
                                                                                         quantity=1.0)['total_excluded']
        # Ahora evaluamos si el UOM de la linea es distinto al UOM del producto
        if line.uom_id.id != line.product_id.uom_id.id:
            # Cambiamos el precio por unidad en base al factor de conversion.
            price_unit *= line.uom_id.factor / line.product_id.uom_id.factor
        # por ultimo verificamos la moneda de la factura y la moneda de la company.
        if invoice.currency_id != invoice.company_id.currency_id:
            price_unit = invoice.currency_id.compute(price_unit, invoice.company_id.currency_id, round=False)
        return price_unit

    # ****************************
    # Modularizacion de impuestos por linea
    def _set_taxes(self):
        """ sobre escribimos la funcion para modularizarla"""
        # *****************************************************************
        # cambiamos este codigo para modularizarlo ya que este se encarga de traer los impuestos para las lineas de la factura
        # if self.invoice_id.type in ('out_invoice', 'out_refund'):
        #     taxes = self.product_id.taxes_id or self.account_id.tax_ids
        # else:
        #     taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids
        # cambiamos por: taxes = self._get_line_taxes()
        # *****************************************************************

        taxes = self._get_line_taxes()

        # Keep only taxes of the company
        company_id = self.company_id or self.env.user.company_id
        taxes = taxes.filtered(lambda r: r.company_id == company_id)

        self.invoice_line_tax_ids = fp_taxes = self.invoice_id.fiscal_position_id.map_tax(taxes, self.product_id,
                                                                                          self.invoice_id.partner_id)

        fix_price = self.env['account.tax']._fix_tax_included_price
        if self.invoice_id.type in ('in_invoice', 'in_refund'):
            prec = self.env['decimal.precision'].precision_get('Product Price')
            if not self.price_unit or float_compare(self.price_unit, self.product_id.standard_price,
                                                    precision_digits=prec) == 0:
                self.price_unit = fix_price(self.product_id.standard_price, taxes, fp_taxes)
        else:
            self.price_unit = fix_price(self.product_id.lst_price, taxes, fp_taxes)

    def _get_line_taxes(self):
        """modularizacion de la obtencion de impuestos por linea de factura"""
        # almacenamos la compañia del usuario
        company = self.company_id or self.env.user.company_id
        if self.invoice_id.type in ('out_invoice', 'out_refund'):
            # vemos si la compañia es RTC
            is_rtc = self.invoice_id._get_is_RTC(company)
            # validamos que la factura sea recibo o RTC para devolver un modelo de impuestos vacios
            if self.invoice_id.siat_bol_sale_type == 'recibo' or is_rtc:
                taxes = self.env['account.tax']
            else:
                taxes = self.dao_get_vendor_taxes(company)
        else:
            taxes = self.product_id.supplier_taxes_id.filtered(
                lambda r: r.company_id.id == company.id) or self.account_id.tax_ids
        return taxes

    def dao_get_vendor_taxes(self, company):
        return self.product_id.taxes_id.filtered(lambda r: r.company_id.id == company.id) or self.account_id.tax_ids

    def set_product_attributes(self):
        """este metodo establece parametors que son refrentes l productos que deben guardarse como historico,
        como ser numero de serie"""
        if self.product_id:
            if not self.product_id.economic_activity:
                raise ValidationError("Producto sin configuración de Actividad Económica")
            if not self.product_id.siat_codigo_producto_sin:
                raise ValidationError("Producto sin configuración de Código de Producto SIAT")
        if self.uom_id and not self.uom_id.siat_product_uom_id:
            raise ValidationError("Unidad de Medida sin configuración de Código SIAT")

        if self.product_id:
            self.update({'siat_is_giftcard': self.product_id.gift_card or False,
                         'siat_numero_serie': self.product_id.barcode if self.product_id.barcode else False,
                         'siat_descripcion': self.product_id.name,
                         'siat_codigo_producto': self.product_id.default_code if self.product_id.default_code else self.product_id.id,
                         'siat_codigo_producto_sin': self.product_id.siat_codigo_producto_sin or False,
                         'siat_actividad_economica': self.product_id.economic_activity.id if self.product_id.economic_activity else False,
                         })

    @api.onchange("product_id")
    def onchange_product(self):
        """ejecutamos un onchange en el caso de que cambie el producto"""
        self.set_product_attributes()

    @api.constrains('quantity')
    def _constrains_quantity(self):
        if self.quantity < 0:
            raise ValidationError(_('No puede ingresar cantidades en negativo'))

    @api.constrains('price_unit')
    def _constrains_price_unit(self):
        if self.price_unit < 0:
            raise ValidationError(_('No puede ingresar precios en negativo'))
