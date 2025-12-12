# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import models
import wizard
import report
from odoo import api, SUPERUSER_ID


def _auto_install_l10n_bo(cr, registry):
    """
    Hook para instalar el accounting de Bolivia en caso de que no este inslado
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Lista de modulos autoinstalables para manejar las cuentas de Bolivia, es decir 'Bolivia - Accounting'
    module_list = ['l10n_bo']

    # Obtenemos los IDs los modulos que esten en la lista y que esten en estado uninstalled
    module_ids = env['ir.module.module'].search([('name', 'in', module_list), ('state', '=', 'uninstalled')])

    if module_ids:
        # Registramos para que se instalen al momento de instalar este modulo
        module_ids.sudo().button_install()


def _update_l10n_bo_tax_config(cr, registry):
    """
    Hook para Actualizar los impuestos IVA (VENTA y COMPRA), IT que se crean al instalar el l10n_bo

    Para tener una correcta configuración de impuestos para BOLIVIA, debemos incluir el impuesto en el precio (price_include),
    usar el cálculo para impuestos (amount_type) 'division -> Percentage of Price Tax Included',
    y por último afecta a los siguientes impuestos (include_base_amount).

    Esta función se llama desde el __opener__.py o lo que ahora se conoce como __manifest__.py

    Hacemos esto en el Hook al instalar este módulo, xq no pudimos sobreescribir la data en los xml.
    """

    env = api.Environment(cr, SUPERUSER_ID, {})
    taxes_xml_ids = ["l10n_bo.ITAX_21", "l10n_bo.OTAX_21", "l10n_bo.ITAX_03"]
    taxes_ids = []

    for xml_id in taxes_xml_ids:
        tax_template = env.ref(xml_id)
        # env.ref(xml_id) retorna la referencia al account.tax.template
        # el que queremos actualizar es el account.tax generado o creado con ese template.
        # por tanto agregamos en el array taxes_id los id que serian de account.tax
        if tax_template and tax_template.id:
            taxes_ids.append(tax_template.id)

    # actualizamos todos los account.tax
    if len(taxes_ids) > 0:
        env['account.tax'].sudo().browse(taxes_ids).write({'amount_type': 'division', 'include_base_amount': True, 'price_include': True})
