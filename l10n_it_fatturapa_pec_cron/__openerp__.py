# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: ElvenStudio
#    Copyright 2015 elvenstudio.it
#    License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
#
##############################################################################
{
    'name': 'Italian Localization - FatturaPA - Emission - PEC Support via cron',
    'version': '8.0.0.1.1',
    'category': 'Localisation/Italy',
    'author': "Elven Studio S.N.C.",
    'summary': 'Send electronic invoices via PEC with CRON',
    'website': 'http://www.elvenstudio.it',
    'license': 'LGPL-3',

    'depends': [
        'account',
        'email_template_qweb',
        'l10n_it_reverse_charge',
        'l10n_it_fatturapa_pec',
    ],

    'data': [
        'data/invoices_with_errors_view_qweb.xml',
        'data/invoices_with_errors_template.xml',

        'data/cron.xml',
        'views/account_invoice.xml',
    ],

    'installable': True,
    'application': False,
}
