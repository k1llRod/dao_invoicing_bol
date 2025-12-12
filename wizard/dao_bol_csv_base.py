# -*- coding: utf-8 -*-
import base64
import StringIO
from openerp import fields, models, api, _
from ..unicode_csv import UnicodeWriter
from openerp.exceptions import UserError


class DaoCSVBaseWizard(models.TransientModel):
    """
    Clase para poder usar el WIZARD BASE con funcionalidad de exportar en CSV un reporte.
    Se hereda de models.TransientModel que permite guardar temporalmente los atributos de esta clase en la BD segun lo que indique el usuario en el WIZARD.
    Despues de generar el reporte, ODOO tiene la logica de borrar estos datos temporales.
    Este models.TransientModel almacena temporalmente para que se pueda usar el concepto de WIZARD, mientras que el models.AbstractModel no almacena nada en la BD, todo esta en memoria para generar el reporte, es decir es el reporte como tal.
    Odoo Tiene en Settings -> Scheduled Action -> Auto Vacuum Internal Data, esta tarea se encarga de eliminar los TransientModels antiguos.
    Este reporte, si no se elige la opcion 'enable_csv', imprime un PDF, caso contrario genera un archivo CSV o TXT, dependiendo si el usuario quiere usar el separador de miles 'csv_with_thousand_separator'
    * Un file CSV es un archivo separado por comas, por definicion, por tanto por ejemplo excel al abrir un csv coloca en cada columna cada valor separador por comas.
    * por tanto si generamos el csv para el SIN y la factura tiene montos >= 1000 (formateados como 1,000.00) excel pondria en 2 columnas en lugar de 1.
    * ejemplo: si tenemos el row NIT|NroFactura|Monto -> 123456|0077|1,560.50 excel abre este valor en 2 columnas, la primera contendria : 123456|0077|1 y la segunda 560.50
    * por tanto si el usuario indica que quiere usar separador de miles, se generara un file .txt para si quiere abrirse en excel, el asistente pregunte si se quiere colocar cada item separado por algo.
    * si el usuario indica NO usar el separador de MILES, Odoo debe quitar la coman en el formato de numeros, y generar el CSV.
    * EL nombre para el FILE a crearse cuando es CSV depende si se usa o no el separador de MILES

    Nos basamos en:
    * account -> wizard -> account_report_common.py  (base)
    * account -> wizard -> account_financial_report.py  (extend)

    Lo que queremos es tener en esta base la funcionalidad para usar la referencia al modulo unicode_csv.
    Después podemos usar esta misma CLASE en otro modulo (ejemplo purchases) bajo el esquema de odoo de '_inherits'
    y no tener que hacer copy & paste del codigo.
    """
    _name = "dao.csv.report.wizard"
    _description = "CSV Report Wizard"

    # COLUMNAS
    # Columna o atributos de la clase para usarse en el WIZARD como input o filtro de datos para el reporte.
    date_start = fields.Date(string='Start Date', default=fields.Date.today())
    date_end = fields.Date(string='End Date', default=fields.Date.today())
    # Adicionamos columnas para exportar el reporte en CSV
    # Basicamente se indica el delimitador, el nombre para el archivo, y el campo donde almacenar temporalmente el archivo.
    # Estos campos solamente se usan si enable_csv es true, caso contrario el reporte se ejecuta de manera normal y se descarga este como PDF sin necesidad de almacenar en un field.Binary
    enable_csv = fields.Boolean(string='Enable CSV')
    csv_delimiter = fields.Char('CSV delimiter', size=1, default='|')
    csv_quotechar = fields.Char('CSV quote character', size=1, default='"')
    csv_name = fields.Char(compute='_set_csv_file_name', string='Export name', readonly=True, store=True, size=50)
    csv_data = fields.Binary('Export', readonly=True)
    csv_with_column_names = fields.Boolean(string='With Column Names')
    # Manjear la logica para mostrar o no el separador de miles en el file CSV o TXT generado.
    csv_with_thousand_separator = fields.Boolean(string='With thousand separator', help='Generate a text file with the amounts formatted with thousands separator, otherwise it creates a .csv file removing the "," to the amounts.')

    # FUNCIONES
    # def _print_report(self, data):
    #     data = self.pre_print_report(data)
    #     # Actualizamos el valor del diccionario 'form' adicionando los campos del model.Trasient del Wizard
    #     data['form'].update({'date_start': self.date_start, 'date_end': self.date_end})
    #     # Ejecutamos del model report, el get_action pasandole el self, el nombre de la templeta qweb a usar y la fuente de datos para el reporte.
    #     return self.env['report'].get_action(self, 'account_extra_reports.report_partnerledger', data=data)
    # Basandonos en el reporte account_report_common.py
    # Creamos una funcion con el decorador @api.multi, porque se tiene el concepto de wizard, por definicion, el wizard deberia poder contener varias instancias y no solamente @api.one
    # por ejemplo de repente tenemos un wizard paso a paso y en el siguiente next del wizard ya no funcionaria si tendriamos una decoracion @api.one.
    #pero si podemos despues validar self.ensure_one() para asegurarnos que el self represente un solo record.

    @api.multi
    def generate_report(self):
        self.ensure_one()

        # Debemos ejecutar la generacion del reporte para CSV o PDF (Normal)
        if self.enable_csv:
            return self._generate_csv()
        else:
            return self._generate_normal()

    def _generate_normal(self):
        """
        Generar el reporte de manera normal.
        Es decir, en base a la definicion del reporte que queramos ejecutar con self.env['report'].get_action,
        Odoo generará el file con el Qweb Templeta, la fuente de datos y hará la descarga en PDF o XLS.
        ESTE METODO SE DEBE EXTENDER EN CADA CLASE O MODEL QUE HEREDA DE ESTA CLASE BASE.
        Por lo tanto este metodo de la BASE NO HACE NADA, como en account -> wizard -> account_report_common.py  (base) en el _print_report.
        """
        # TypeError: exceptions must be old-style classes or derived from BaseException, not unicode
        # raise (_('Error!'), _('Not implemented.'))
        raise UserError(_('Error!\nNot implemented.'))

    def _generate_csv(self):
        """
        Generar el reporte de manera CSV.
        Es decir, generar un archivo CSV con los datos para el SIN.
        Se usa el separador y el quotechar que especifica el usuario, caso contrario '|' (pipe) como separador y '"' (comilla Doble) como quotechar.
        ESTE METODO SE DEBE EXTENDER EN CADA CLASE O MODEL QUE HEREDA DE ESTA CLASE BASE.
        Por lo tanto este metodo de la BASE NO HACE NADA.
        Por lo tanto este metodo de la BASE NO HACE NADA, como en account -> wizard -> account_report_common.py  (base) en el _print_report.
        """
        raise UserError(_('Error!\nNot implemented.'))

    def _get_report_name_without_extension(self):
        """
        Obtiene uno STRING con el nombre para el reporte sin extension
        ESTA FUNCION se puede extender en cada CLASE EXTEND para cambiar el nombre en cada extension
        Caso contrario siempre se llamara como se indica en la BASE
        """
        return 'Libro_iva'

    def _make_and_save_csv(self, arrHeaders=[], arrRows=[]):
        """
        Generar un FILE csv en base a una cabecera y filas especificadas.
        Guarda en el campo 'csv_data' del model TransientModel, para que despues se puede descargar este file.
        Ninguno de los campos son obligatorios.

        """

        # Generate the CSV data.
        csv_data = StringIO.StringIO()
        csv_writer = UnicodeWriter(
            csv_data,
            delimiter=str(self.csv_delimiter),
            quotechar=str(self.csv_quotechar)
        )

        # Verificar si debemos crear el csv con nombres de las columnas, es decir la primera fila contenga o no los nombres
        # NIT | RAZONSOCIAL | NUMEROFACTURA | NUMEROAUTORIZACION | FECHA |IMPORTE TOTAL FACTURA| IMPORTE ICE|IMPORTE EXCENTO|IMPORTE SUJETO A DEB. FISCAL | DEBITOFISCAL |ESTADO|CODIGO DE CONTROL
        # EL campo DEBITO FISCAL solamente va el 13 % del IVA
        # El campo IMPORTE SUJETO A DEB. FISCAL seria lo que llamamos Importe Neto
        if arrHeaders and len(arrHeaders) > 0:
            # Write the first line (field names).
            csv_writer.writerow(arrHeaders)

        # Escribimos cada linea del reporte como linea para el csv
        # en la instancia del FILE CSV en memoria.
        for line in arrRows:
            # Escribimos la linea en el CSV pasandole un array (cada item es el valor de cada columna)
            csv_writer.writerow(line)

        # Save the CSV data in a field so the user can then download it.
        # Guardamos el File CSV, en la columna self.csv_data
        self.write({'csv_data': base64.encodestring(csv_data.getvalue() or u'\n'), })

    @api.one
    @api.depends('date_start', 'date_end', 'enable_csv', 'csv_with_thousand_separator')
    def _set_csv_file_name(self):
        """
        Obtiene el Nombre para el FILE a generar cuando se establece usar o no CSV y si se usara con separador de miles o no.
        This decorator '@api.depends' will trigger the call to the decorated function if any of the fields specified in the decorator is altered by ORM or changed in the form.
        El nombre para el FILE cuando es CSV se le agrega el rango de fechas para que se pueda tener en este la referencia o filtro usado para generar el file.
        """

        if self.enable_csv:
            strName = self._get_report_name_without_extension()
            # Creamos variables para tener el rango de fechas en String con el formato yyyymmdd
            strStart = self._get_integer_date(self.date_start)
            strEnd = self._get_integer_date(self.date_end)
            # La extension por defecto es csv
            strExt = 'csv'

            # La extension se cambia, si el usuario indica usar separador de miles.
            if self.csv_with_thousand_separator:
                strExt = 'txt'

            # Armamos el nombre: ejemplo 'libro_ventas_iva_20160101_20161231.csv'
            self.csv_name = '%s_%s_%s.%s' % (strName, strStart, strEnd, strExt)
        else:
            self.csv_name = ''

    def _get_integer_date(self, strDate):
        """
        Retorna una Fecha String a su correspondiente valor entero, es decir format -> YYYYYMMDD
        El campos strDate es usado como viene desde ODOO field.Date(), que viene por ejemplo 2016-10-06
        :param strDate: String que representa una FECHA.
        :type strDate: string
        """

        # Primero transformamos el valor STRING a DATE
        d = fields.Date.from_string(strDate)

        return d.strftime('%Y%m%d')

    def _format_amount(self, objReportFormat, amount):
        """
        Formatear el valor de un monto, utilizando la instancia del reporte libro de ventas IVA que tiene el formato para numeros de Bolivia (Impuestos - SIN).
        Y toma en cuenta si es para generar un CSV (quitar el separador de MILES ',' coma) o si es para un TXT
        :param objReportFormat: Referencia al objeto pool que tiene la funcion 'bol_format'
        :type objReportFormat: Model pool
        :param amount: Amonto
        :type amount: float
        """
        # amount_formated = "0.0"

        # if not objReportFormat:
        #     objReportFormat = self.env['report.dao_invoicing_bol.report_sales_iva_bol']

        # amount_formated = objReportFormat.bol_format(amount)

        # if not self.csv_with_thousand_separator:
        #     # quitamos la coma, xq sabemos el bol_format el separador de miles es ','
        #     amount_formated = amount_formated.replace(',', '')

        # return amount_formated
        amount_formated = "0.0"

        if amount:
            amount_formated = "{:,.2f}".format(amount)  # 1,000.00 estilo anglosajón

            if not self.csv_with_thousand_separator:
                # Quitamos separador de miles, dejamos el punto decimal
                amount_formated = amount_formated.replace(',', '')

        return amount_formated

    def _build_contexts(self, data):
        """
        Obtiene un diccionario con la fecha de inicio y fecha final indicadas en el formulario Wizard.
        """
        result = {}
        result['date_start'] = data['form']['date_start'] or False
        result['date_end'] = data['form']['date_end'] or False
        return result
