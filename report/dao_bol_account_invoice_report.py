# -*- coding: utf-8 -*-
from openerp import api, models, _
from openerp.tools.amount_to_text_en import amount_to_text as base_amount_to_text
# from dao_invoicing_bol.tools.amount_to_text_es import amount_to_text as bol_amount_to_text
from ..tools.amount_to_text_es import amount_to_text as bol_amount_to_text
from odoo.addons.siat_sin_bolivia.tools import siat_tools as st

from openerp.exceptions import ValidationError


class DaoBolAccountInvoiceReport(models.AbstractModel):
    """
    Clase para customizar el reporte de impresion de factura con formato del SIN.
    el CUSTOM consiste en formatear los montos usando un handler funcion para no mostrar el simbolo de la moneda.
    ya que el widget monetary si o si lo muestra.
    Tambien tiene la funcionalidad de obtener el valor LITERAL (texto) de un determinado monto (float)
    """
    # el nombre debe empezar con <report>. + <Nombre del Modulo>. + <nombre del reporte>
    # el nombre del reporte es el mismo que se lo llama desde account_report.xml
    _name = "report.dao_invoicing_bol.report_invoice_sin"

    # Funcion para manejar el formato con separadores de miles y decimales.
    def bol_format(self, value, precision=2, currency_obj=None, context=None):
        """
        Funcion para formatear un determinado valor al formato monto con separadores de miles y decimales
        y segun lo que se especifique simbolo de moneda.
        basandonos en la funcionalidad de ir_qweb.py (class FloatConverter, MonetaryConverter)
        https://www.odoo.com/forum/help-1/question/how-to-format-numbers-in-qweb-reports-odoov8-89377
        """
         # --- Solución: Manejar valores None ---
        if value is None:
            value = 0.0  # Convertir None a 0.0 para evitar errores
        fmt = '%f' if precision is None else '%.{precision}f'
        # podriamos manejar directamente el formato 'es_BO'?
        lang_code = self.env.context.get('lang') or 'en_US'
        # lang = self.pool['res.lang']
        lang = self.env['res.lang']
        lang_id = lang._lang_get(lang_code)
        # No es NECESARIO verificar esto *****
        # Si el contexto es es_BO verificar que se tenga instalado, caso contrario usar en_US que viene por default en ODOO.
        # if lang_code == 'es_BO' and lang.search_count([('code', '=', lang_code)]) == 0:
        #     # usamos el lang_code que viene por defecto en ODOO
        #     lang_code = 'en_US'
        # **** Odoo lang.format llama a _lang_get y si no obtiene el lang_code usa el por defecto de odoo en_US

        # formatted = lang.format(self.env.cr, self.env.uid, [lang_code], fmt.format(precision=precision), value, grouping=True, monetary=True)
        # MIGRADO
        formatted = lang_id.format(fmt.format(precision=precision), value, grouping=True, monetary=True)

        # Agregamos el simbolo de la moneda si se establecio el currency_obj
        if currency_obj:
            if currency_obj.position == 'before':
                formatted = currency_obj.symbol + '' + formatted
            else:
                formatted = formatted + '' + currency_obj.symbol

        return formatted

    def bol_qty_format(self, qty, uom_id, uom_unit_id=None, precision=2):
        """
        Retorna un valor con o sin decimales, dependiendo del uom (unit of Mesuare) y si el QTY tiene decimales.
        por ejemplo se puede tener el uom 'UNIDAD', pero el qty es 0.5 es decir media Unidad.
        Usamos la funcion is_integer() del tipo de dato float para verificar si qty tiene o no decimales.

        :param qty: Cantidad a formatear.
        :type qty: Float
        :param uom_id: Unit of Mesuare de la cantidad.
        :type uom_id: Integer
        :param uom_unit_id: Unit of Mesuare de la UNIDAD (default = NONE).
        :type uom_unit_id: Integer
        :param precision: Cantidad a formatear (defaul = 2).
        :type precision: Float
        """
        bolToInteger = False

        # solo se va comprobando y transformando el qty si el uom_id es = al uom_unit_id
        # Si no se especifica que ID es de uom_unit_id, se lo obtiene usando la funcion '_get_uom_unit_id'
        if not uom_unit_id:
            uom_unit_id = self._get_uom_unit_id()

        # Vemos si tramos la cantidad como entero o no.
        # Verificamos si el uom_id es el mismo uom de la UNIDAD.
        if uom_id == uom_unit_id:
            # verificamos si qty tiene decimales
            if isinstance(qty, (int, long)):
                bolToInteger = True
            elif isinstance(qty, (float)):
                # Podemos usar la funcion is_integer q retorna True, si no existe parte decimal, ejem: 1.0, 2.0, 0.0
                bolToInteger = qty.is_integer()

        # Transformamos a Integer o formateamos usando la precision de decimales que queremos.
        if bolToInteger:
            return int(qty)
        else:
            return self.bol_format(qty, precision)

    # Funcion para transformar un valor monto a su valor texto literal.
    def bol_amount_to_text(self, amount, currency):
        """
        Basandonos en los aplicado en LeDistrict y revisando el codigo Nativo de ODOO, solamente se tiene el amount_to_text (Belgica - Frances) y amount_to_text_en (Inlges)
        por tanto se debe crear un modulo TOOL para la traduccion en español para Bolivia
        """
        # No se tiene los nombres (largos) en el modelo currency, solamente abreviaciones
        # por tanto manejaremos para dolares, euros y bolivianos, los demas casos se usaran su determinado name o abreviacion

        # obtenemos el detalle del currency
        # currency = self.env['res.currency'].browse(currency_id)
        currency_name = currency.name.upper().strip()
        boolUseBol = True

        # Obtenemos el Nombre LARGO
        if currency_name == 'EUR':
            currency_name = 'Euros'
        elif currency_name == 'USD':
            currency_name = 'Dólares'
        elif currency_name == 'BOB':
            currency_name = 'Bolivianos'
        else:
            # Caso contrario se queda con el currency.name (abreviado)
            # Y se usa la traduccion en ingles.
            boolUseBol = False

        # Obtener el monto a su Literal en texto
        if boolUseBol:
            return bol_amount_to_text(amount, currency=currency_name)
        else:
            return base_amount_to_text(amount, currency=currency_name)

    def bol_importe_base_gasolina(self, invoice_id):
        """
        Obtiene el Detalle del Importe BASE del invoice y retorna si este se ve afectado por productos de tipo gasolina o no.
        """
        # print "K32 bol_importe_base_gasolina invoice_id", invoice_id
        # print "K32 bol_importe_base_gasolina self", self

        objInvoice = self.env['account.invoice'].browse(invoice_id)

        # print "K32 bol_importe_base_gasolina objInvoice", objInvoice

        dicImporte = objInvoice._bol_get_importe_base()
        # print "K32 bol_importe_base_gasolina dicImporte", dicImporte

        return {'has_gasoline': dicImporte['TieneGasolina'],
                'importe_base': dicImporte['ImporteBase'],
                }

    def _get_uom_unit_id(self):
        """
        Obtenemos el ID que representa el Unit of Mesuare (uom) de la medidad Unidad(es) o Unit(s)
        Es muy importante usar el formato [NOMBRE MODULO].[ID DATA] en self.ref()
        Ya que si no colocamos el [NOMBRE MODULO], nos da el error (si llamamos a la funcion desde QWEB:
        [ File "/opt/odoo/odoo-server/openerp/addons/base/ir/ir_model.py", line 970, in xmlid_lookup
          module, name = xmlid.split('.', 1)
          QWebException: "need more than 1 value to unpack" while evaluating
        ]

        De esta manera es dificil entender el error, xq creemos que la ejecucion o llamada de una funcion desde Qweb es la incorrecta.
        Pero como tal sucede en el lado de la funcion que usa self.env.ref() incorrectamente.
        """
        return self.env.ref('product.product_uom_unit').id

    def _get_doc_args(self, docs, docids, strReportModel, uom_unit_id):
        """
        Modularizamos la obtención del diccionario docargs.
        De esta manera despues podemos extender esto, por ejemplo para despues pasarle indicar si es para generar una COPIA de la factura.
        docs: Instancia a los modelos, en este caso deberian ser account.invoice, con .Browse usando los ids que se especifica en docids
        """
        # Generamos el Diccionario docargs y lo retornamos
        docargs = {
            'bol_format': self.bol_format,
            'bol_amount_to_text': self.bol_amount_to_text,
            'bol_importe_base': self.bol_importe_base_gasolina,
            'doc_ids': docids,
            'doc_model': strReportModel,
            'docs': docs,
            'uom_unit_id': uom_unit_id,
            'bol_qty_format': self.bol_qty_format,
        }

        return docargs

    # Sobreescribimos la funcion render_html para adicionar el handler a la funcion bol_format y poder llamarla desde las templetas qweb
    # @api.multi
    # def render_html(self, data=None):
    # MIGRADO ahora el render recibe los docids y ya no existe el self._ids
    @api.model
    def render_html(self, docids, data=None):
        """
        Funcionalidad para agregar el handler a la funcion bol_format para ser usado en el render del reporte qweb
        """
        # El nombre del reporte tiene que tener el nombre del modulo + nombre del reporte
        strReportName = 'dao_invoicing_bol.report_invoice_sin'
        # Creamos la instancia a report pool
        report_obj = self.env['report']
        # Obtenemos la intancia al reporte
        report = report_obj._get_report_from_name(strReportName)

        # Creamos un diccionario de datos para pasar al render del report
        # y el handler para la funcion

        # En algunos reportes se usa el valor de una variable para obtener los DOCS
        # # docs = self.env[self.model].browse(self.env.context.get('active_ids', []))
        # en la documentacion en docs, esta yendo self, pero self es toda la clase 'report.dao_invoicing_bol.report_invoice_sin'
        # y al parecer genera una excepcion xq docs no representa el model account.invoice
        # asi que primero obtendremos la intancia de los models en base a los _ids
        # docs = self.env[report.model].browse(self._ids)
        docs = self.env[report.model].browse(docids)

        # Primero validamos que todos los invoices sean por ventas
        arrSalesType = ["out_invoice", "out_refund"]
        # Para ello usamos el domain [["type", "in", ["out_invoice", "out_refund"]]]
        # para que para compras el domain es [["type", "in", ["in_invoice", "in_refund"]]]
        # print "K32 validamos tipo de reporte."
        if any(invoice for invoice in docs if invoice.type not in arrSalesType or not invoice.siat_bol_generated):
            # Tomar nota q como se lanza un mensaje cuando el reporte esta como PDF se muestra este.
            # Pero si esta en tipo HTML dara un mensaje SERVER ERROR General
            raise ValidationError(_('You can only print sales invoices and invoices generated for SIN.'))

        for inv in docs:
            dic_docs = self.get_inv_dics(inv)

        # Obtenemos el ID del uom_unit y pasarlo como parametro en docargs
        # y ahi hacemos la verificacion para mostrar o no la cantidad como entero.
        uom_unit_id = self._get_uom_unit_id()

        # docargs = {
        #     'bol_format': self.bol_format,
        #     'bol_amount_to_text': self.bol_amount_to_text,
        #     'bol_importe_base': self.bol_importe_base_gasolina,
        #     # 'doc_ids': self._ids,
        #     'doc_ids': docids,
        #     'doc_model': report.model,
        #     # 'docs': self,
        #     'docs': docs,
        #     'uom_unit_id': uom_unit_id,
        #     'bol_qty_format': self.bol_qty_format,
        # }
        docargs = self._get_doc_args(dic_docs, docids, report.model, uom_unit_id)
        # docargs = self._get_doc_args(docs, docids, report.model, uom_unit_id)

        # Mandamos a hacer el render del reporte
        return report_obj.render(strReportName, docargs)

    # metodo que arme diccionario get_inv_dics con for porque puede ver mas de un docs
    def get_inv_dics(self, ob_inv):
        inv_array = []
        # todo: debemos reemplazar la logica de los campos antiguos con la data que recopilamos en diccionario en cada factura
        dict_inv = ob_inv.get_invoice_data_dict()
        dic_docs = {'company_logo': ob_inv.company_id.logo,
                    'use_razon_social': ob_inv.company_id.siat_use_razon_social,
                    'company_srs': ob_inv.company_id.siat_razon_social or False,
                    'company_name': ob_inv.company_id.name,
                    'codigo_punto_venta': ob_inv.siat_invoice_channel.selling_point_code,
                    'siat_entity_title': ob_inv.siat_invoice_channel.bol_entity_title,
                    'siat_direction': ob_inv.siat_invoice_channel.direction,
                    'company_phone': ob_inv.company_id.phone,
                    'siat_municipality': ob_inv.siat_invoice_channel.municipality,
                    'com_coun_name': ob_inv.company_id.country_id.name,
                    'siat_channel_rts': ob_inv.siat_invoice_channel.bol_is_rts,
                    'company_nit': str(ob_inv.company_id.siat_nit),
                    'siat_numero_factura': ob_inv.siat_numero_factura,
                    'siat_cuf': ob_inv.siat_cuf,
                    'siat_razon_social': dict_inv['siat_nombre_razon_social'],
                    'siat_fecha_emision': st.iso_strdt_to_dt_odoo(ob_inv.siat_date_time).strftime("%Y-%m-%d %H:%M"),
                    'siat_numero_documento': dict_inv['siat_numero_documento'],
                    'siat_complemento': dict_inv['siat_complemento'],
                    'cod_cliente': ob_inv.partner_id.cod_cliente_siat,
                    'siat_amount_total': ob_inv.amount_total - ob_inv.siat_monto_gift_card,
                    'siat_currency_id': ob_inv.currency_id,
                    'siat_bol_sub_total': ob_inv.amount_untaxed_before_global_discounts,
                    'siat_bol_total_discount': ob_inv.siat_bol_total_discount,
                    'siat_bol_global_discount': ob_inv.amount_global_discount,
                    'amount_total': ob_inv.amount_total,
                    'siat_monto_gift_card': ob_inv.siat_monto_gift_card,
                    'siat_bol_code_qr': ob_inv.siat_bol_code_qr,
                    'caption_1': ob_inv.siat_invoice_channel.bol_invoice_caption_1,
                    'caption_2': self.env['leyenda.factura'].get_random_record().descripcion_leyenda,
                    'caption_3': ob_inv.siat_invoice_channel.bol_invoice_caption_3,
                    'caption_4': ob_inv.siat_invoice_channel.bol_invoice_caption_4,
                    'offline': '1' if ob_inv.siat_offline else '0',
                    'siat_status': ob_inv.siat_status,
                    'siat_cod_doc_sector': str(ob_inv.siat_invoice_channel.type_doc_sector.codigo_clasificador),
                    'siat_name_student': dict_inv['siat_name_student'] or False,
                    'siat_periodo_inv': dict_inv['siat_periodo_inv'] or False,
                    'inv_lines': [],
                    }

        # 'caption_2': ob_inv.siat_invoice_channel.bol_invoice_caption_2,
        # contador para las lineas
        count = 0
        for line in ob_inv.invoice_line_ids:
            count += 1
            net = line.quantity * line.price_unit
            desc = net * (line.discount / 100)
            subt = net - desc
            dic_line = {'siat_codigo_producto': line.siat_codigo_producto,
                        'siat_cantidad': line.quantity, # line.siat_cantidad,
                        'siat_uom_id': line.uom_id.id,
                        'siat_uom_name': line.uom_id.siat_product_uom_id.descripcion,
                        'siat_name': line.name,
                        'siat_price_unit': line.price_unit,
                        'siat_discount': desc,
                        'sub_total': subt,
                        }
            dic_docs['inv_lines'].append(dic_line)
        inv_array.append(dic_docs)
        return inv_array


# class DaoBolAccountInvoiceCopyReport(models.AbstractModel):
#     """
#     Extension de DaoBolAccountInvoiceReport para imprimir la COPIA de la Factura.
#     """
#     # el nombre debe empezar con <report>. + <Nombre del Modulo>. + <nombre del reporte>
#     # el nombre del reporte es el mismo que se lo llama desde account_report.xml
#     _name = "report.dao_invoicing_bol.report_invoice_copy_sin"
#     _inherit = "report.dao_invoicing_bol.report_invoice_sin"
#
#     # Extendemos
#     def _get_doc_args(self, docs, docids, strReportModel, uom_unit_id):
#         """
#         Extendemos la funcionalidad BASE para que al Diccionario de docargs, se le agregue el KEY ITEM copy: True
#         """
#
#         # import pudb;pudb.set_trace()
#
#         docargs = super(DaoBolAccountInvoiceCopyReport, self)._get_doc_args(docs, docids, strReportModel, uom_unit_id)
#
#         # Adicionamos el KEY que indica es se debe generar como copia
#         docargs["copy"] = True
#
#         return docargs
