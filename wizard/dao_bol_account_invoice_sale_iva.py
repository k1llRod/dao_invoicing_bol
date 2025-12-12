# -*- coding: utf-8 -*-
from openerp import models, _
from datetime import datetime
# from openerp.exceptions import UserError


class DaoAccountInvoiceSaleIVAWizard(models.TransientModel):
    """
    Clase para poder usar el WIZARD y generar el reporte del libro de ventas IVA.
    Se hereda de models.TransientModel (desde el enfoque python) que permite guardar temporalmente los atributos de esta clase en la BD segun lo que indique el usuario en el WIZARD.
    Despues de generar el reporte, ODOO tiene la logica de borrar estos datos temporales.
    Se hereda de dao_bol_csv_base (desde el enfoque odoo), se debe si o si cambiar el _name, _description.
    Asi como indicar la funcionalidad '_generate_normal' y '_generate_csv'.
    Si quisieramos poder adicionar otras columnas si vemos necesario para el wizard extendido.
    """
    # Heredamos del dao_bol_csv_base
    _inherit = "dao.csv.report.wizard"
    # Extendemos el Nombre del WIZARD, DESCIPCION para ser distintos de la BASE.
    # por tanto ODOO creara otro model trasient con este nombre que contendra los valores del wizard para ventas que son distintos a los de la BASE.
    _name = "dao.account.invoice.sale.iva.report.wizard"
    _description = "Sales IVA Report Wizard"

    def _get_report_name_without_extension(self):
        """
        Extendemos la funcion para que el nombre tenga relacion a VENTAS.
        """
        return 'libro_ventas_iva'

    def _generate_normal(self):
        """
        SOBREESCRIBIMOS la funcionalidad de la CLASE BASE que no hace nada (Lanza una excepcion de no implementado).
        Generar el reporte de manera normal.
        Es decir, en base a la definicion del reporte que queramos ejecutar con self.env['report'].get_action,
        Odoo generará el file con el Qweb Templeta, la fuente de datos y hará la descarga en PDF o XLS.
        """
        # Generamos el Diccionario DATA para pasar a una instancia del reporte que queramos realizar.
        data = {}
        data['ids'] = self.env.context.get('active_ids', [])
        data['model'] = self.env.context.get('active_model', 'ir.ui.menu')
        # No es necesario que le pasemos las columnas relacionadas a CSV, xq no son usadas en el REPORTE PDF como tal.
        # Usamos el READ para que ya nos pase como un diccionario
        data['form'] = self.read(['date_start', 'date_end'])[0]
        used_context = self._build_contexts(data)
        # Creamos un diccionar para el contexto y lo agregamos al diccionario data en el key used_context
        data['form']['used_context'] = dict(used_context, lang=self.env.context.get('lang', 'en_US'))
        # return self._print_report(data)
        # Ejecutamos del model report, el get_action pasandole el self, el nombre del reporte que tenemos en el tag report en views->account_report.xml y la fuente de datos para el reporte.
        return self.env['report'].get_action(self, 'dao_invoicing_bol.report_sales_iva_bol', data=data)

    def _generate_csv(self):
        """
        SOBREESCRIBIMOS la funcionalidad de la CLASE BASE que no hace nada (Lanza una excepcion de no implementado).
        Generar el reporte de manera CSV.
        Es decir, generar un archivo CSV con los datos para el SIN.
        Se usa el separador y el quotechar que especifica el usuario, caso contrario '|' (pipe) como separador y '"' (comilla Doble) como quotechar.
        """

        # Obtenemos los DATOS para el CSV usando la logica del objeto reporte 'report_sales_iva_bol'
        objReport = self.env['report.dao_invoicing_bol.report_sales_iva_bol']
        # Obtenemos el detalle del reporte, es decir las lineas con todos los invoices
        rep_lines = objReport._get_rep_lines(self.date_start, self.date_end, sortedby=True)

        # Generate the CSV data.
        arrHeader = []
        arrRows = []

        # Verificar si debemos crear el csv con nombres de las columnas, es decir la primera fila contenga o no los nombres
        # NIT | RAZONSOCIAL | NUMEROFACTURA | NUMEROAUTORIZACION | FECHA |IMPORTE TOTAL FACTURA| IMPORTE ICE|IMPORTE EXCENTO|IMPORTE SUJETO A DEB. FISCAL | DEBITOFISCAL |ESTADO|CODIGO DE CONTROL
        # EL campo DEBITO FISCAL solamente va el 13 % del IVA
        # El campo IMPORTE SUJETO A DEB. FISCAL seria lo que llamamos Importe Neto
        if self.csv_with_column_names:
            # Write the first line (field names).
            arrHeader = [
                'No',
                'ESPECIFICACION',
                'FECHA DE LA FACTURA',
                'No DE LA FACTURA',
                'CODIGO DE AUTORIZACION',
                'NIT/CI CLIENTE',
                'COMPLEMENTO',
                'NOMBRE O RAZON SOCIAL',
                'IMPORTE TOTAL DE LA VENTA',
                'IMPORTE ICE',
                'IMPORTE IEHD',
                'IMPORTE IPJ',
                'TASAS',
                'OTROS NO SUJETOS AL IVA',
                'EXPORTACIONES Y OPERACIONES EXENTAS',
                'VENTAS GRAVADAS A TASA CERO',
                'SUBTOTAL',
                'DESCUENTOS BONIFICACIONES Y REBAJAS SUJETAS AL IVA',
                'IMPORTE GIFT CARD',
                'IMPORTE BASE PARA DEBITO FISCAL',
                'DEBITO FISCAL',
                'ESTADO',
                'CODIGO DE CONTROL',
                'TIPO DE VENTA',
            ]

        # Escribimos cada linea del reporte como linea para el csv
        for line in rep_lines:
            arrRow = [
                line['nro'], # No
                line['bol_especificacion'], # ESPECIFICACION
                datetime.strptime(line['date_invoice'], '%Y-%m-%d').strftime('%d/%m/%Y'), # FECHA DE LA FACTURA
                str(int(line.get('siat_numero_factura') or 0)),  # No DE LA FACTURA
                line['siat_cuf'], # CODIGO DE AUTORIZACION
                line['partner_nit'], # NIT/CI CLIENTE
                line['partner_complement'], # COMPLEMENTO
                line['partner_name'], # NOMBRE O RAZON SOCIAL
                self._format_amount(objReport, line['bol_total_amount']), # IMPORTE TOTAL DE LA VENTA
                
                self._format_amount(objReport, line['bol_total_ice']), # IMPORTE ICE
                self._format_amount(objReport, line['bol_total_ice']), # IMPORTE IEHD
                self._format_amount(objReport, line['bol_total_ice']), # IMPORTE IPJ
                self._format_amount(objReport, line['bol_total_ice']), # TASAS
                self._format_amount(objReport, line['bol_total_ice']), # OTROS NO SUJETOS AL IVA
                
                self._format_amount(objReport, line['bol_total_exemption']), # EXPORTACIONES Y OPERACIONES EXENTAS
                self._format_amount(objReport, line['bol_total_tasa_cero']), # VENTAS GRAVADAS A TASA CERO
                self._format_amount(objReport, (line['siat_bol_sub_total'])), # SUBTOTAL
                self._format_amount(objReport, line['bol_total_discount']), # DESCUENTOS BONIFICACIONES Y REBAJAS SUJETAS AL IVA
                self._format_amount(objReport, line['gift_card']), # IMPORTE GIFT CARD 
                self._format_amount(objReport, line['bol_total_base_import']), # IMPORTE BASE PARA DEBITO FISCAL
                self._format_amount(objReport, line['iva_amount']), # DEBITO FISCAL
                line['bol_state'], # ESTADO
                line['bol_control_code'], # CODIGO DE CONTROL
                line['es_gift'],# TIPO DE VENTA siat_bol_sale_type
            ]

            # Escribimos la linea en el CSV pasandole un array (cada item es el valor de cada columna)
            # csv_writer.writerow(arrRow)
            # Cada Item es un array de valores
            arrRows.append(arrRow)

        # Save the CSV data in a field so the user can then download it.
        # Guardamos el File CSV, en la columna self.csv_data
        self._make_and_save_csv(arrHeader, arrRows)

        # Obtenemos el ID del VIEW (wizard - mensaje) que indica que se genero correctamente el CSV File
        # y permite descar el FILE
        # view_obj = self.pool.get('ir.ui.view')
        # view_id = view_obj.search(cr, uid, [('name', '=', 'account_general_ledger_view_csv_done')])
        view_id = self.env['ir.ui.view'].search([('name', '=', 'dao_account_invoice_sale_iva_report_wizard_csv_done')]).id

        # Retornamos el Diccionario con los fatos para indicar al usuario que puede descargar el FILE CSV
        return {
            'name': _('Sales IVA CSV'),
            # Pasamo el ID de self.id xq este model tiene el csv_data para poder ser descargado.
            # Tomar en cuenta que este model es Trasient, es decir se almacena temporalmente los datos durante un determinado tiempo en la BD.
            'res_id': self.id,
            # Colocamos como model el mismo que pusimos al WIZARD
            'res_model': 'dao.account.invoice.sale.iva.report.wizard',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'view_id': view_id,
            'view_mode': 'form',
            'view_type': 'form',
        }
