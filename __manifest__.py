# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# No es necesario poner dependencia a product, xq account ya tiene esta dependencia.

# NOTA.- MUY importante que el view del wizard dao_bol_control_code_test_view.xml este arriba de company_view.xml
# en la lista de data: [] para evitar el  'error external id not found'
{
    'name': 'DAO Invoicing Bolivia',
    'version': '1.0',
    'summary': 'Implementar normativa del Servicio Nacional de Impuestos.',
    'description': """
Invoicing
====================
Adecuacion de la impresion de facturas para usar llaves de dosificacion, codigo QR, codigo de control, nro. de autorizacion, nro. de factura, NIT de cliente

Registra o almacena los valores necesarios en la impresion de factura para poder reimprimir la factura.

Adiciona la posibilidad de imprimir Recibos
    """,
    'author': 'DAO SYSTEMS',
    'category': 'Accounting & Finance',
    'website': 'https://www.dao-systems.com',
    'images': [],
    'depends': ['account', 'l10n_bo', 'dao_account_cancel_bol', 'siat_sin_bolivia'],
    'external_dependencies': {'python': ['Crypto']},
    'data': ['security/move_cancellation_security.xml',
             'security/ir.model.access.csv',
             'views/account_report.xml',
             'data/account_invoicing_bol_data.xml',
             'data/product_data.xml',
             'views/account_invoice_view.xml',
             # 'views/account_tax_view.xml',
             # 'views/company_view.xml',
             'views/partner_view.xml',
             'views/product_view.xml',
             'views/account_payment_view.xml',
             # 'views/res_config_view.xml',
             'views/report_invoice.xml',
             'views/report_invoice_sales_iva.xml',
             'views/account_payment_view.xml',
             'views/siat_payment_codes.xml',
             'wizard/dao_bol_control_code_test_view.xml',
             'wizard/dao_bol_reset_numbering_view.xml',
             'wizard/dao_bol_account_invoice_sale_iva_view.xml',
             'wizard/wizard_invoice_generate_siat_view.xml',
             ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': '_update_l10n_bo_tax_config',
}
