# -*- coding: utf-8 -*-

# import logging
# from openerp.http import request
from openerp import api, fields, models

# _logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    """
    Extension de la clase product_template para adicionar al producto una propiedad que indique si se debe tratar como gasolina o no en la venta de este.
    """
    _inherit = 'product.template'

    bol_is_gas = fields.Boolean(string="Gasoline", default=False, help="Specify if the product will be treated like gasoline in a sales order line.")
    # por solicitud del cliente jugueteria mundo ternura, deberia existir un campo marca, el nombre en ingles o nombre con el que exportan y otro campo mas de notas general
    # odoo ya manajeba el concepto de 'description', pero lo quitaron en la version 10 pero solo de la vista, no del model
    # https://github.com/odoo/odoo/issues/19279, por tanto se puede volver a colocar para que se muestre este valor y ya no crear otro field.
    # por mas que tengamos para cotizacion, para compras o para inventario , asi como tb los mensajes para grupos de followers o logs del producto.
    # Tomar en cuenta que son campos referenciales, por tanto no son obligatorios.
    # Marca del producto
    bol_brand = fields.Char(string='Brand', size=50, help='Brand of the product')
    # Otro Nombre, especificamos que no sea traducible, xq pueden colocar como otro nombre, el nombre en otro idioma
    bol_name_2 = fields.Char(string='Name 2',
                             size=50,
                             translate=False,
                             help='Another name for the product.\n\n'
                                  'For example: The name for the producto in other language'
                             )

    def get_message_body(self, vals):
        res = []
        if vals:
            for val in vals:
                # para no duplicar la logica del diccionario y que sea sostenible, lo llamamos directamente de product product asi solo tenemos que extender un metodo
                fields = self.env['product.product'].dic_to_get_field_for_message() or {}
                if val and val in fields:
                    old_value = self.getfield(val) if self.getfield(val) else 'Vacio'
                    new_value = vals[val] if vals[val] else 'Vacio'
                    if isinstance(old_value, float) or isinstance(old_value, int):
                        old_value = str(old_value)
                    if isinstance(new_value, float) or isinstance(new_value, int):
                        new_value = str(new_value)
                    try:
                        res.append('from ' + str(fields[val]) + ': ' + str(old_value) + ' to ' + str(fields[val]) + ': ' + str(new_value) or '')
                    except:
                        pass
        return res

    def check_is_number(self, value):
        return True

    @api.model
    def getfield(self, field_name):
        if field_name and len(self) == 1:
            value = self
            for part in field_name.split('.'):
                value = getattr(value, part)
            return value
        else:
            return ''

    @api.multi
    def write(self, vals):
        for item in self:
            res = item.get_message_body(vals)
            if res:
                item.message_post(body=(str(res)))
        res = super(ProductTemplate, self).write(vals)
        return res

    @api.model
    def default_get(self, fields):
        """
        Estendemos el Defaul_get que es una funcionalidad BASE del ORM model.
        Debemos Verificamos si esta configurado para multicompany.
        Si es el caso, para el campo taxes_id (si esta en field) obtener todos de todas las compañias.
        """
        res = super(ProductTemplate, self).default_get(fields)

        # import pudb; pudb.set_trace()
        # if self.env.user.has_group('base.group_multi_company'):
        #     tax_ids = []
        #     # Primero vemos los impuestos de ventas.
        #     if 'taxes_id' in fields:
        #         # Obtenemos los TAXES para ventas (IT e IVA)
        #         tax_ids = self._get_sales_taxes_ids()
        #         if tax_ids and len(tax_ids) > 0:
        #             # Obtenemos el diccionario con el formato correspondiente en VALUES para los impuestos.
        #             sales_taxes = self._get_convert_to_default_format('taxes_id', tax_ids)
        #             # reemplazamos de RES los impuestos por default de ventas.
        #             # para que tengamos todos los IVA e ITs de todas las companies
        #             res['taxes_id'] = sales_taxes['taxes_id']

        #     # Ahora vemos los impuestos de compras.
        #     if 'supplier_taxes_id' in fields:
        #         tax_ids = self._get_purchases_taxes_ids()
        #         if tax_ids and len(tax_ids) > 0:
        #             # Obtenemos el diccionario con el formato correspondiente en VALUES para los impuestos.
        #             purchases_taxes = self._get_convert_to_default_format('supplier_taxes_id', tax_ids)
        #             # reemplazamos de RES los impuestos por default de compras.
        #             # para que tengamos todos los IVAde todas las companies
        #             res['supplier_taxes_id'] = purchases_taxes['supplier_taxes_id']

        return res

    def _get_convert_to_default_format(self, key, value):
        """
        Retorna un diccionario con KEY y VALUE con el formator necesario para que ODOO pueda usar
        Es decir, la funcion nativa 'default_get' genera un diccionario con KEYs de todos los fields que se solicitaron para obtener los valores por default.
        y los valores de cada KEY del diccionario tiene un formato de TUPLAS MODELS IDs

        :param key: Nombre o KEY a manejar, por ejemplo 'taxes_id' (VENTAS) o 'supplier_taxes_id' (COMPRAS)
        :type key: string
        :param value: Arreglo de IDs, por ejemplo IDs de impuestos para ventas o de Impuestos para compras.
        :type value: Array[int]
        """

        # Retornamos un Diccionario, por tanto creamos un diccionario inicial con los datos recibidos.
        # Generamos un diccionario como lo hace la BASE default_get (openerp->models.py[]1336)
        # para tener el formato de tuplas y models necesario
        # 1 un diccionario simpple KEY:VALUE donde el VALUE contiene el array de IDs de impuestos
        # Ejemplo: {'taxes_id': [3, 1, 4, 5, 7, 6]}
        res = {key: value}

        # 2 modificamos el Diccionario para tener en el VALUE el Model(ids)
        # ejemplo: {'taxes_id': account.tax(3, 1, 4, 5, 7, 6)}
        res = self._convert_to_cache(res, validate=False)
        # 3 POr ultimo modificamos el diccionario para que el value sea TUPLAS de valores model, ids
        # Ejemplo: {'taxes_id': [(5,), (4, 3), (4, 1), (4, 4), (4, 5), (4, 7), (4, 6)]}
        res = self._convert_to_write(res)

        return res

    def _get_sales_taxes_ids(self, bolAll=True):
        """
        Obtenemos el ID del TAX IVA de ventas utilizando regular expresion en POSTGRESQL
        para que el WHERE de la sentencia filtre los impuestos que empiecen con IVA o IT y sean de uso para VENTAS.

        Tomar en cuenta:

        donde ~* es para igualar la expresion de manera insensitive
        \m es para especificar q empiece con iva
        \M es para especificar q termine con venta
        .* es escape y concanedado

        select * from account_tax where name ~* '\miva.*venta\M';

        bolAll: por defecto es para q BUSQUE IVA e IT, caso contrario solo IVA
        """
        tax_ids = []
        if bolAll:
            query = "SELECT id, name, type_tax_use FROM account_tax WHERE type_tax_use='sale' AND (name ~* '\miva.*' OR name ~* '\mit.*')"
        else:
            query = "SELECT id, name, type_tax_use FROM account_tax WHERE type_tax_use='sale' AND name ~* '\miva.*'"

        self.env.cr.execute(query)

        tax_ids = [r[0] for r in self.env.cr.fetchall()]

        return tax_ids

    def _get_purchases_taxes_ids(self):
        """
        Obtenemos el ID del TAX IVA de compras utilizando regular expresion en POSTGRESQL
        para que el WHERE de la sentencia filtre los impuestos que empiecen con IVA y sean de uso para COMPRAS.

        Tomar en cuenta:

        donde ~* es para igualar la expresion de manera insensitive
        \m es para especificar q empiece con iva
        \M es para especificar q termine con venta
        .* es escape y concanedado

        """
        tax_ids = []
        query = "SELECT id, name, type_tax_use FROM account_tax WHERE type_tax_use='purchase' AND name ~* '\miva.*'"
        self.env.cr.execute(query)

        tax_ids = [r[0] for r in self.env.cr.fetchall()]

        return tax_ids


class ProductUOM(models.Model):
    """
    Extension de la clase product_oum para adicionar una propiedad 'shortcode' o abreviacion del unit o measure.

    Ejemplo: de Unit(s) el shortcode seria U, Liter(s) seria L , de Kg seria Kg.

    Esta columna no es un campo obligatorio.
    Este campo se lo puede usar al momento de imprimir una factura por ejemplo para colocar la abreviación de la Unidad de medida, en lugar de todo el Nombre.
    """
    _inherit = 'product.uom'

    bol_shortcode = fields.Char(string='Short Code', required=False, size=10, help='Short code (shortcut) for unit of measure, it means unit of measure abbreviated. Example: Liter(s) -> L or Unit(s) -> U')


class ProductProduct(models.Model):
    _inherit = "product.product"

    def get_message_body(self, vals):
        res = []
        if vals:
            for val in vals:
                fields = self.dic_to_get_field_for_message() or {}
                if val and val in fields:
                    old_value = self.getfield(val) if self.getfield(val) else 'Vacio'
                    new_value = vals[val] if vals[val] else 'Vacio'
                    if isinstance(old_value, float) or isinstance(old_value, int):
                        old_value = str(old_value)
                    if isinstance(new_value, float) or isinstance(new_value, int):
                        new_value = str(new_value)
                    try:
                        res.append('from ' + str(fields[val]) + ': ' + str(old_value) + ' to ' + str(fields[val]) + ': ' + str(new_value) or '')
                    except:
                        pass
        return res

    @api.model
    def getfield(self, field_name):
        if field_name and len(self) == 1:
            value = self
            for part in field_name.split('.'):
                value = getattr(value, part)
            return value
        else:
            return ''

    @api.model
    def dic_to_get_field_for_message(self):
        """para logear mas campos simplemente aumentamos los mismo a este diccionario la idea es que si en el value a cabiar existe en nuestro diccionario
        procedemos a agregarlo a nuestro log, en la izquieda debe ir el nombre de campo como tal en el codigo y a la derecha como queremos q se vea en el mensaje"""
        res = {'name': 'Name',
               'list_price': 'Sale price',
               'default_code': 'Internal Reference',
               'categ_id': 'Internal Category',
               'standard_price': 'Cost'
               }
        return res

    @api.multi
    def write(self, vals):
        for item in self:
            res = item.get_message_body(vals)
            if res:
                item.message_post(body=(str(res)))
                item.product_tmpl_id.message_post(body=(str(res)))
        res = super(ProductProduct, self).write(vals)
        return res