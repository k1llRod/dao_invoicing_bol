# -*- coding: utf-8 -*-
import math
import logging
# from openerp.http import request
from openerp import api, fields, models
# from openerp.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    """
    Extension de la clase account.tax para adicionar los campos necesarios para distinguir si es un impuesto ICE o no.
    Tambien se agrega logica para obtener en base a una regla de 3 simple y uom (unit of measures) la alicouta correspondiente a este impuesto.
    Para el SIN de Bolivia, el ICE (impuesto consumo especifico) FIJO es un monto por cada LITRO que se debe pagar.
    Por tanto ICE tiene un un grupo de IMPUESTOS el FIJO y el PORCENTUAL y segun DECRETO se debe aplicar para cierto productos.
    Por ejemplo Bebida Alcoholica VODKA tiene un ICE Porcentual y un ICE Fijo (Bs/Litro), mientras que los Cigarrillos solamente tiene un ICE Porcentual.
    """
    _inherit = "account.tax"

    # columnas para adicionar a la clase base.
    bol_ice = fields.Boolean(string="Is ICE", default=False, help="It indicates that the tax is ICE or not.")

    # adicionamos un tag para usar en los impuestos que seran usados para descuento
    bol_is_for_discount = fields.Boolean(string="Use for Discount", default=False,
                                         help="Use this tax to apply it to the process of discounts on accounting entries.")
    # en caso de que el impuesto se use en la logica de descuentos en movimientos contables
    discount_account_id = fields.Many2one('account.account', string='Discount Account',
                                          help="For Bolivian regulations, it is necessary to include the respective lines of discounts in the sales entries and discount purchases, using specific accounts for this purpose.")
    # como la cuenta del debito o credito fiscal sera siempre la opsueta a la cuenta registrada en el impuesto sera necesario
    # configurarla de igual manera
    discount_tax_account_id = fields.Many2one('account.account', string='Discount Tax Account',
                                          help="For Bolivian regulations, it is necessary to include the respective lines of discounts in the sales entries and discount purchases, using specific accounts for this purpose.")
    # Metodos a extender

    @api.multi
    def copy(self, default=None):
        """
        Extender el COPY para que tambien tome en cuenta la propiedad es ICE o no.
        """

        # Basandos en el copy de la BASE nosotro hacemos algo parecido pero con la propiedad bol_ice
        # Basicamente es crear un diccionario si es que es NONE y adicionar un KEY bol_ice con el valor de la clase
        # despues le pasamos a la clase BASE que hara lo mismo pero con el valor Nombre antes de ya mandar al metodo BASE de models de Odoo para que haga el copy.
        default = dict(default or {}, bol_ice=self.bol_ice)
        return super(AccountTax, self).copy(default=default)

    def _compute_amount(self, base_amount, price_unit, quantity=1.0, product=None, partner=None):
        """
            EXTENSION de la clase BASE account - account.py - AccountTax para manejar si el TAX es ICE o no.
            Distinguir si el ICE es Especifico y en Base a la uom obtener el valor en Litros y usando una regla de 3 calcular el impuesto.
            Returns the amount of a single tax. base_amount is the actual amount on which the tax is applied, which is
            price_unit * quantity eventually affected by previous taxes (if tax is include_base_amount XOR price_include)
            La Logica de la Clase BASE es:
            if self.amount_type == 'fixed':
                return math.copysign(self.amount, base_amount) * quantity
            if (self.amount_type == 'percent' and not self.price_include) or (self.amount_type == 'division' and self.price_include):
                return base_amount * self.amount / 100
            if self.amount_type == 'percent' and self.price_include:
                return base_amount - (base_amount / (1 + self.amount / 100))
            if self.amount_type == 'division' and not self.price_include:
                return base_amount / (1 - self.amount / 100) - base_amount
        """
        # Tomar en cuenta que el modulo product en product_data tiene records para categorias y uom por defecto.
        # las obtendremos en BASE a su id de record , por ejemplo:
        # self.env.ref('product.product_uom_categ_unit')
        # self.env.ref('product.product_uom_categ_vol')
        # self.env.ref('product.product_uom_litre')
        # self.env.ref('dao_invoicing_bol.dao_product_uom_750ml')

        # .ref() := Environment method returning the record matching a provided external id

        # if request.debug:
        #     print "K32 def _compute_amount DETALLE:"
        #     print "K32 TAX SELF", self
        #     print "K32 TAX SELF.name", self.name.encode('utf-8')
        #     print "K32 base_amount", base_amount
        #     print "K32 price_unit", price_unit
        #     print "K32 quantity", quantity
        #     print "K32 product", product
        #     print "K32 partner", partner

        tax_amount = 0.00

        # Al igual q la BASE llamamos a ensure_one, esto solamente para asegurarnos que la instancia SELF represente un objeto accountTax y no un array de objetos
        # basicamente ensure_one evalua: assert len(self) == 1, 'Expected Singleton'
        self.ensure_one()

        # Verificamos si el Impuestos es ICE y fixed (Alicuota especifico) y si el uom del product es VOLUMEN para poder aplicar el concepto Bs/Litro
        # por tanto el Product no debe ser None
        # para cualquier otro caso, se usa el calculo normal de la BASE, por tanto se puede tener ICE FIJO pero sin regla de 3

        boolRegla3 = False
        if product and self.bol_ice and self.amount_type == 'fixed':

            # Obtenemos el ID de la Categoria VOLUME
            volume_id = self.env.ref('product.product_uom_categ_vol').id

            # if request.debug:
            #     print "K32 product NAME:", product.name
            #     print "K32 product.uom ID:", product.uom_id
            #     print "K32 product.uom NAME:", product.uom_id.name
            #     print "K32 volume_id:", volume_id

            # verificamos que el uom del product sea Volumen
            # if product.uom_id.category_id.name.lower() == "volume":
            if product.uom_id.category_id.id == volume_id:
                boolRegla3 = True

        if boolRegla3:
            # Sabemos que el uom de referencia de la categoria VOLUME es Litros al instalar ODOO
            # obtenemos el valor en Litros, puede ser que el producto ya use esta unidad, sino convertirlo

            # Inicialmente el valor qyt_lts es el valor quantity, por ejemplo si queremos 2 botellas de vodka donde su uom es Litro, entonces se aplica el ICE a los 2 Litros.
            qyt_lts = quantity

            # verificamos el uom del producto.
            liters_id = self.env.ref('product.product_uom_litre').id

            # if request.debug:
            #     print "K32 liters_id:", liters_id

            # Si no es Litro, debemos transformarlo a uom BASE referencial (para VOLUME es Litro)
            if product.uom_id.id != liters_id:
                ProductUom = self.env['product.uom']
                # obtenemos el valor el Litros (por tanto no debemo usar el to_uom_id de la funcion de uom)
                # def _compute_qty(self, cr, uid, from_uom_id, qty, to_uom_id=False, round=True, rounding_method='UP'):
                # product.uom_id._compute_qty(
                # qty = ProductUom._compute_qty(line.product_uom.id, line.product_uom_qty, line.product_id.uom_id.id)
                qyt_lts = ProductUom._compute_qty(product.uom_id.id, quantity, liters_id)

                # if request.debug:
                #     print "K32 qyt_lts:", qyt_lts

            # Usamos la misma logica que la BASE para el TYPE fixed
            # math.copysign(x,y) := retorna el valor de X con el signo de y, ejemplo: math.copysign(1.0, -0.0):= -1.0
            # multiplicamos el monto del IMPUESTO por la Cantidad en Litros, xq se quiere monto_ICE por cada Litro
            tax_amount = math.copysign(self.amount, base_amount) * qyt_lts
        else:
            tax_amount = super(AccountTax, self)._compute_amount(base_amount, price_unit, quantity, product, partner)

        # if request.debug:
        #     print "K32 tax_amount:", tax_amount
        #     print "K32 FIN _compute_amount **********************"

        return tax_amount
