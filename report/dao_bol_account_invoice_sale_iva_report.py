# -*- coding: utf-8 -*-

# from datetime import datetime
import time
from openerp import api, models
# Para performar el SORT usamos el itemgetter que es mucho mas eficiente que el lambda exp.
from operator import itemgetter
from datetime import datetime

class ReportSalesIVABOL(models.AbstractModel):
    _name = 'report.dao_invoicing_bol.report_sales_iva_bol'

    # # Funcion para manejar el formato con separadores de miles y decimales.
    def bol_format(self, value, precision=2, currency_obj=None, context=None):
        """
        Funcion para formatear un determinado valor al formato monto con separadores de miles y decimales

        Llamamos al MODEL report.dao_invoicing_bol.report_invoice_sin q ya tiene este método
        """
        # Obtener los ID de taxes COMPRAS (en este CASO en compras, la funcion _get_purchases_taxes_ids solo maneja IVA compra no hay IT)
        return self.env['report.dao_invoicing_bol.report_invoice_sin'].bol_format(value, precision, currency_obj, context)

    def bol_date_format(self, value):
        """

        :param value:
        :return:
        """
        return datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y')

    def _sum_totals(self, data):

        # basandonos en el report-> account_partner_ledger de account_extra_reports

        # Obtenemos el ID del TAX IVA Ventas.
        tax_id = self._get_tax_iva_id()

        result = {  'total_company_signed': 0.0,
                    'total_untaxed': 0.0,
                    'total_untaxed_signed': 0.0,
                    'total_amount': 0.0,
                    'total_amount_signed': 0.0,
                    'total_tax': 0.0,
                    'total_exemption': 0.0,
                    'total_discount': 0.0,
                    'total_gift_card': 0.0,
                    'total_base': 0.0,
                    'total_subtotal': 0.0,
                    'total_ice': 0.0,
                    'total_iva': 0.0,
                }

        date_start = data['form']['date_start']
        date_end = data['form']['date_end']

        query = """SELECT   SUM(a.amount_total_company_signed) as total_company_signed,
                            SUM(a.amount_untaxed) as total_untaxed,
                            SUM(a.amount_untaxed_signed) as total_untaxed_signed,
                            SUM(a.amount_total) as total_amount,
                            SUM(a.amount_total_signed) as total_amount_signed,
                            SUM(a.amount_tax) as total_tax,
                            SUM(a.bol_total_exemption) as total_exemption,
                            SUM(a.bol_total_discount) as total_discount,
                            SUM(a.siat_monto_gift_card) as total_gift_card,
                            SUM(a.bol_total_base) as total_base,
                            SUM(a.siat_bol_sub_total) as total_subtotal,
                            SUM(a.dao_total_ice) as total_ice,
                            SUM(IVA.amount) as total_iva
                            FROM    account_invoice a
                            INNER JOIN res_partner p ON a.partner_id = p.id
                            INNER JOIN (SELECT id, invoice_id, tax_id, amount
                                        FROM  account_invoice_tax
                                        WHERE tax_id = %i) IVA ON a.id = IVA.invoice_id
                            WHERE   a.siat_bol_generated = True
                            AND a.type IN ('out_invoice','out_refund')
                            AND a.date_invoice BETWEEN '%s' AND '%s';
                """ % (tax_id, date_start, date_end)

        # Ejecutamos el QUERY de suma de totales.
        self.env.cr.execute(query)
        contemp = self.env.cr.fetchone()
        # print "K32: _sum_totals contemp => ", contemp
        # el fetchone() retorna una TUPLA (Valor1, Valor2,..... ValorN)
        # por tanto verificamos que todos los items esten llenos con la funcion ALL.
        if contemp is not None:
            result['total_company_signed'] = contemp[0] or 0.0
            result['total_untaxed'] = contemp[1] or 0.0
            result['total_untaxed_signed'] = contemp[2] or 0.0
            result['total_amount'] = contemp[3] or 0.0
            result['total_amount_signed'] = contemp[4] or 0.0
            result['total_tax'] = contemp[5] or 0.0
            result['total_exemption'] = contemp[6] or 0.0
            result['total_discount'] = contemp[7] or 0.0
            result['total_gift_card'] = contemp[8] or 0.0
            result['total_base'] = contemp[9] or 0.0
            result['total_subtotal'] = contemp[10] or 0.0
            result['total_ice'] = contemp[11] or 0.0
            result['total_iva'] = contemp[12] or 0.0

        # print "K32: _sum_totals => ", result

        return result

    def _get_totals(self, lines):
        """
        Obtener un diccionario con los totales de los monto de un arreglo o lista de diccionarios, resultante del query del render_html

        Usando una solucion mas, 'pythonnesque' http://stackoverflow.com/questions/14180866/sum-each-value-in-a-list-of-tuples
        Ejemplo:

        Tenemos una lista o array de diccionarios:
        l = [{'quantity': 10, 'price': 5},{'quantity': 6, 'price': 15},{'quantity': 2, 'price': 3},{'quantity': 100, 'price': 2}]

        obtenemos los totales de Cantidad (sumando Cantidad) y Precio (Sumando el calculo de precio por cantidad)
        (total_quantity, total_price) = (
                                        sum(x) for x in zip(*((item['quantity'],
                                                               item['price'] * item['quantity'])
                                                              for item in l)))

        En lugar de hacer el clasico:

        total_quantity = 0
        total_price = 0
        for item in l:
             total_quantity += item['quantity']
             total_price += item['price'] * item['quantity']

        """

        result = {  'total_company_signed': 0.0,
                    'total_untaxed': 0.0,
                    'total_untaxed_signed': 0.0,
                    'total_amount': 0.0,
                    'total_amount_signed': 0.0,
                    'total_tax': 0.0,
                    'total_exemption': 0.0,
                    'total_discount': 0.0,
                    'total_gift_card': 0.0,
                    'total_base': 0.0,
                    'total_subtotal': 0.0,
                    'total_ice': 0.0,
                    'total_iva': 0.0,
                    'total_tasa_cero': 0.0,
                }

        if lines and len(lines) > 0:
            (total_company_signed,
             total_untaxed,
             total_untaxed_signed,
             total_amount,
             total_amount_signed,
             total_tax,
             total_exemption,
             total_discount,
             total_gift_card,
             total_base,
             total_subtotal,
             total_ice,
             total_iva) = (
                sum(x) for x in zip(*(
                    (
                        item.get('amount_total_company_signed', 0.0) or 0.0,
                        item.get('amount_untaxed', 0.0) or 0.0,
                        item.get('amount_untaxed_signed', 0.0) or 0.0,
                        item.get('siat_bol_sub_total', 0.0) or 0.0,
                        item.get('amount_total_signed', 0.0) or 0.0,
                        item.get('amount_tax', 0.0) or 0.0,
                        item.get('bol_total_exemption', 0.0) or 0.0,
                        item.get('bol_total_discount', 0.0) or 0.0,
                        item.get('siat_monto_gift_card', 0.0) or 0.0,
                        item.get('bol_total_base_import', 0.0) or 0.0,
                        (item.get('siat_bol_sub_total', 0.0) or 0.0)
                        - (item.get('bol_total_ice', 0.0) or 0.0)
                        - (item.get('bol_total_exemption', 0.0) or 0.0),
                        item.get('bol_total_ice', 0.0) or 0.0,
                        item.get('iva_amount', 0.0) or 0.0
                    )
                    for item in lines
                ))
            )
            # Establecemos los valores al diccionario de respuesta
            result['total_company_signed'] = total_company_signed
            result['total_untaxed'] = total_untaxed
            result['total_untaxed_signed'] = total_untaxed_signed
            result['total_amount'] = total_amount
            result['total_amount_signed'] = total_amount_signed
            result['total_tax'] = total_tax
            result['total_exemption'] = total_exemption
            result['total_discount'] = total_discount
            result['total_gift_card'] = total_gift_card
            result['total_base'] = total_base
            result['total_subtotal'] = total_subtotal
            result['total_ice'] = total_ice
            result['total_iva'] = total_iva

        # print "K32: _get_totals => ", result
        return result

    def _get_sorted_lines(self, lines):
        """
        Ordenar la Lista de lineas (diccionarios) ordenados por FECHA y NRO. de Factura.
        """
        if lines and len(lines) > 1:
            # Ordenamos por Fecha y numero de la factura.
            # sorted(lines, key = lambda l: (l['date_invoice'], l['bol_nro']))
            # Usando el itemgetter es mucho mas rapido y limpio.
            lines = sorted(lines, key=itemgetter('date_invoice', 'bol_auth_nro', 'bol_nro'))
            # lines = sorted(lines, key=itemgetter('bol_auth_nro', 'date_invoice', 'bol_nro'))
            nro = 1
            for line in lines:
                line['nro'] = str(nro)
                nro += 1
        return lines

    def _get_tax_iva_id(self):
        # Tratamos de obtener el ID del TAX desde el XML ID que se tiene en el modulo l10n_bo
        # Usamos el TRY por si da error, en caso de no existir o si ocurrio un error.
        # intentamos obtener el ID usando regular expresion en POSTGRESQL para trael el ID q empiece con IVA y termine en VENTAS
        tax_id = -1

        # Podria lanzarse una excepcion: ValueError: External ID not found in the system: l10n_bo.ITAX_21
        # si es no se instalo el modulo l10n_bo o si se elimino el parametro desde la interfaz de usuario.
        # por tanto usamos el TRY y usamos la otra funcion regular_expresion para obtener el id de otra manera.
        try:
            tax_id = self._get_tax_iva_id_by_xmlid()
        except Exception, e:
            tax_id = -1

        if tax_id <= 0:
            tax_id = self._get_tax_iva_id_by_regex()

        return tax_id

    def _get_tax_iva_id_by_xmlid(self):
        """
        Obtenemos el ID del TAX IVA de ventas que se tiene o se crea desde el módulo l10n_bo
        """
        # xml_record = self.env.ref("module_name.seq_type_ean13_sequence")
        xml_record = self.env.ref("l10n_bo.ITAX_21")

        # print "K32: _get_tax_iva_id_by_xmlid => ", xml_record

        if xml_record:
            return xml_record.id
        else:
            return -1

    def _get_tax_iva_id_by_regex(self):
        """
        Obtenemos el ID del TAX IVA de ventas utilizando regular expresion en POSTGRESQL para que el WHERE de la sentencia filtre los impuestos que empiecen con IVA y terminen con VENTAS.

        Tomar en cuenta:

        donde ~* es para igualar la expresion de manera insensitive
        \m es para especificar q empiece con iva
        \M es para especificar q termine con venta
        .* es escape y concanedado

        select * from account_tax where name ~* '\miva.*venta\M';

        """
        tax_id = -1
        query = "SELECT id, name, type_tax_use FROM account_tax WHERE name ~* '\miva.*venta\M'"

        self.env.cr.execute(query)

        contemp = self.env.cr.fetchone()
        # print "K32: _get_tax_iva_id_by_regex => ", contemp

        if contemp is not None:
            tax_id = contemp[0] or -1

        return tax_id

    def _get_taxes_iva_id_by_regex(self):
        """
        Obtenemos el/los IDs del TAX IVA de ventas, es decir todos los que empiezan con IVA

        Llamamos al MODEL producto q contiene el metodo _get_sales_taxes_ids, para no duplicar codigo
        """
        # Obtener los ID de taxes VENTAS pero SOLO IVA no queremos los de IT mas.
        return self.env['product.template']._get_sales_taxes_ids(bolAll=False)

    def _get_sql_query(self, user_company, taxes_id, date_start, date_end, sortedby=False):
        """
        Obtener un STRING SQL QUERY en base a los parametros.

        EL QUERY es de los INVOICES de VENTAS JOIN Impuestos IVA
        """
        """
        to do el campo bol_total_tasa_cero ira por defecto cero "0" ya que aun no manejamos este tipo de venta
        para ello es necesario crear un tipo de item tasa cero y su respectivo calculo de montos
        se llamo a impuestos nacionales en fecha 30-08-17 para recabar esta informacion, las transacciones incluidas
        para este tipo de venta son venta de libros nacionales y transporte internacional

        Tomar en cuenta que ahora se puede tener Facturas por COBRAR, y las del POS tb se las quiere imprimir en el libro de Ventas
        por mas que no se hayan contabilizado todavia, como ya se emiten, se quiere poder tenerlas en este reporte.

        Por tanto en lugar de usar WHEN 'paid' THEN [VALOR] WHEN 'cancel' THEN 0 ahora usamos WHEN 'cancel' ELSE [VALOR]
        """

        query = """SELECT   a.id,
                            '' as nro,
                            a.date_invoice,
                            a.number,
                            a.move_name,
                            a.state,
                            a.type,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.amount_total_company_signed
                            END as amount_total_company_signed,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.amount_untaxed
                            END as amount_untaxed,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.amount_untaxed_signed
                            END as amount_untaxed_signed,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.amount_total
                            END as amount_total,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.amount_total_signed
                            END as amount_total_signed,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.amount_tax
                            END as amount_tax,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.residual
                            END as residual,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.bol_total_exemption
                            END as bol_total_exemption,
                            a.partner_id,
                            CASE a.state
                                WHEN 'cancel' THEN 'ANULADA'
                                ELSE coalesce(a.bol_client_name, p.name)
                            END as partner_name,
                            p.nit as partner_nit,
                            p.dao_cpl_personal as partner_complement,
                            CASE a.state
                                WHEN 'cancel' THEN '0'
                                ELSE a.bol_nit
                            END as bol_nit,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.siat_bol_total_discount
                            END as bol_total_discount,
                            a.bol_auth_nro,
                            a.siat_cuf,
                            COALESCE(NULLIF(a.bol_control_code, ''), '0') AS bol_control_code,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE (a.siat_bol_sub_total - a.dao_total_ice - a.bol_total_exemption - 0)
                            END as bol_sub_total,
                            a.siat_bol_sub_total,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.siat_bol_sub_total
                            END as bol_total_amount,
                            a.bol_nro,
                            a.siat_numero_factura,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE a.dao_total_ice
                            END as bol_total_ice,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE coalesce(IVA.amount, 0)
                            END as iva_amount,
                            CASE a.state
                                WHEN 'cancel' THEN 'A'
                                ELSE 'V'
                            END as bol_state,
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE 0
                            END as bol_total_tasa_cero,
                            
                            CASE a.state
                                WHEN 'cancel' THEN 0
                                ELSE (a.siat_bol_sub_total - a.siat_bol_total_discount - a.siat_monto_gift_card)
                            END as bol_total_base_import,
                            
                            a.siat_monto_gift_card as gift_card,
                            COALESCE(NULLIF(a.bol_specification, ''), '2') AS bol_especificacion,
                            a.siat_bol_sale_type,
                            
                            CASE 
                                WHEN t.descripcion ILIKE '%%GIFT%%' THEN 1
                                ELSE 0
                            END as es_gift
                    FROM    account_invoice a
                            INNER JOIN res_partner p ON a.partner_id = p.id
                            INNER JOIN tipo_metodo_pago t ON a.siat_codigo_metodo_pago = t.id
                            LEFT OUTER JOIN (SELECT id, invoice_id, tax_id, amount
                                                FROM  account_invoice_tax
                                            WHERE tax_id IN %s) IVA ON a.id = IVA.invoice_id
                    WHERE a.siat_bol_sale_type IN ('factura', 'manual')
                        AND a.company_id = %i
                        AND a.type IN ('out_invoice','out_refund')
                        AND a.date_invoice BETWEEN '%s' AND '%s';
                """ % (taxes_id, user_company, date_start, date_end)
        #     quitamos la sentencia where AND a.state in ('paid','cancel') para que traiga todas las facturas con el campo bol_generated = true
        print("CONSULTA SQL: ", query)
        return query

    def _get_rep_lines(self, date_start, date_end, sortedby=False):
        """
        Obtiene las Lineas para el reportes segun el filtro de fecha inicio y fecha fin.
        Modularizamos esta funcion para que pueda ser llamada desde la logica para el reporte CSV
        Para el SIN, el estado es V (VALIDA) o A (ANULADO), E (Extraviada) N (No utilizada) C (Emitida en contigencia) L (Libre consignacion)
        Por nuestra logica en ODOO solamente podemos tener V o A, donde 'V' son todas las facturas con estado 'paid' y 'A' son todas las facturas con estado 'cancel'
        Tomar encuenta que solo aparece la opcion 'CANCEL' si instalamos la extension account_cancel 'Cancel Journal Entries' (quitando el filtro de Apps)
        De igual manera para impuestos los valores a reportar deben esta en 0 si el estado es 'A', por tanto solo para reportar estos, cambiamos su valor a 0 en el select, ya que para ODOO y nuestros controles internos estos valores NO DEBEMOS MODIFICAR.
        :param date_start: Fecha Inicial para filtrar
        :type date_start: date
        :param date_end: Fecha Final para filtrar
        :type date_end: date
        :param sortedby: Indica si se debe ordenar o no por Fecha y Nro. de factura la lista de lineas
        :type sortedby: boolean
        """
        # Obtenemos el ID de company del usuario actual
        user_company = self.env.user.company_id.id
        # company = self.env['res.company']._company_default_get('account.invoice')

        # Obtenemos los IDs de los TAXES IVA Ventas para que sea de todas las companies que tenemos.
        taxes_id = self._get_taxes_iva_id_by_regex()
        # transformamos para que sean TUPLAS y con los parentesis para que despues el STRING format las transforme en (1,2,3,......N)
        # taxes_id = "%s" % (tuple(taxes_id),)
        # Si el array de IDs retorna un solo id, tuple retorna (1,) algo q el SQL no puede interpretar.
        # por tanto usamos JOIN para concatenar los ID separados por comas
        # ahora como los ID son iteger usamos map (str , array) para q cada item lo transforme a string poder concatenar, sino da una excepcion
        # ",".join(map(str, a))
        taxes_id = "(%s)" % ",".join(map(str, taxes_id))

        query = self._get_sql_query(user_company, taxes_id, date_start, date_end, sortedby)

        # Ejecutamos el QUERY y obtenemos un array de diccionarios con todas las filas
        self.env.cr.execute(query)
        rep_lines = self.env.cr.dictfetchall()

        if sortedby:
            return self._get_sorted_lines(rep_lines)
        else:
            return rep_lines

    # @api.multi
    # def render_html(self, data):
    # MIGRADO ahora el render recibe los docids y ya no existe el self._ids
    @api.model
    def render_html(self, docids, data=None):
        # print "K32: render_html data => data"
        # basandonos en el report-> account_partner_ledger de account_extra_reports

        date_start = data['form']['date_start']
        date_end = data['form']['date_end']

        # Ejecutamos un QUERY para obtener las lineas para el reporte
        rep_lines = self._get_rep_lines(date_start, date_end, sortedby=True)

        # Obtenemos los ID de los Invoices que tenemos en el array diccionario
        invoice_ids = [invoice['id'] for invoice in rep_lines]

        # Obtenemos los totales de los montos, del array de rep_lines
        # para que ya no tengamos que pasarle el al reporte un handler a la funcion self._sum_totals.
        totals = self._get_totals(rep_lines)

        # ahora el Objeto diccionario de argumentos para el reporte es un poco distinto
        # detail: Representa el array de diccionario de items para el reporte.
        # Tiene un handler para la funcion _sum_totals.
        # como se llama a .render, esta funcion agrega company, parnet, etc.
        docargs = {
            'doc_ids': invoice_ids,
            # 'doc_model': None,
            'doc_model': self.env['account.invoice'],
            'data': data,
            'docs': self.env['account.invoice'].browse(invoice_ids),
            'time': time,
            # 'sum_totals': self._sum_totals,
            'totals': totals,
            'bol_format': self.bol_format,
            'bol_date_format': self.bol_date_format,
            'detail': rep_lines
        }

        # print "K32: render_html docargs => ", docargs

        # Ejecutamos el render del reporte indicando que QWEB TEMPLATE (q esta en views) se debe usar y todo el DocArgs.
        return self.env['report'].render('dao_invoicing_bol.report_invoice_sales_iva', docargs)
