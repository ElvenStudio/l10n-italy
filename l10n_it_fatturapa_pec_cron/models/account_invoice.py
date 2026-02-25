# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: ElvenStudio
#    Copyright 2015 elvenstudio.it
#    License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
#
##############################################################################

from openerp import api, models, fields, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    fatturapa_out_error = fields.Boolean(
        string=_('With issues during last export'),
        help=_('If is set to true, then invoice had issues '
               'during last export via cron'),
        default=False,
        readonly=True
    )

    @api.multi
    def action_fatturapa_out_error_resolved(self):
        self.message_post(
            subject=_('E-invoice errors marked as resolved'),
            body=_('User %s has marked e-invoice errors as resolved') % self.env.user.name
        )
        return self.write({'fatturapa_out_error': False})

    @api.model
    def cron_send_invoices_with_errors(self):
        # Get invoices with error
        invoices_with_error_ids = self.search([('fatturapa_out_error', '=', True)])

        # Generate email and send email
        if invoices_with_error_ids:
            invoice_action_id = self.env.ref('account.action_invoice_tree1')
            email_vals = self.env['email.template'].with_context(
                invoices_with_error=invoices_with_error_ids,
                base_url=self.env['ir.config_parameter'].get_param('web.base.url'),
                invoice_action_id=invoice_action_id.id,
            ).generate_email(
                self.env.ref('l10n_it_fatturapa_pec_cron.email_template_invoices_with_errors_qweb').id,
                1
            )
            self.env['mail.mail'].create(email_vals).send()

        return True
