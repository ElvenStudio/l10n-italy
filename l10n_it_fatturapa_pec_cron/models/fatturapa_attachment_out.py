# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: ElvenStudio
#    Copyright 2015 elvenstudio.it
#    License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
#
##############################################################################

from openerp import api, models, _
from openerp.exceptions import except_orm, ValidationError


class FatturaPAAttachmentOut(models.Model):
    _inherit = 'fatturapa.attachment.out'

    @api.model
    def get_invoices_to_send_domain(self):
        # ATTENZIONE: Variazioni ADE - Specifiche tecniche versione 1.7
        # Per quanto riguarda le operazioni passive, dal 01/07/2022 diventa obbligatorio l'invio XML di fatture per:
        # - Intra-UE: acquisto di beni => tramite emissione documento di integrazione elettronico  (TD18)
        # - Intra-UE: acquisto di servizi => tramite emissione documento di integrazione elettronico   (TD17)
        # - acquisto di beni per ex art.17 c.2 DPR 633/72 => tramite Integrazione/autofattura  (TD19)
        # - Extra-UE: acquisti di servizi => tramite emissione di autofatture elettroniche  (TD17)
        # - Extra-UE: acquisti di beni Extra-UE => nulla invece dovrà essere fatto perché accompagnati da bolletta doganale.

        rc_journals = self.env['account.rc.type'].search([]).mapped('journal_id')
        domain = [
            ('state', 'in', ['open', 'paid']),
            ('type', 'in', ['out_invoice', 'out_refund']),
            ('fatturapa_attachment_out_id', '=', False),  # skip already exported
            ('fatturapa_out_error', '=', False),  # skip with errors
            ('date_invoice', '>=', '2019-01-01'),

            # considering different cases, before and after 2022-07-01 v.1.7
            '|',

            # exclude RC invoices before 2022-07-01 (to send via Esterometro)
            '&',
            ('date_invoice', '<', '2022-07-01'),
            ('journal_id', 'not in', rc_journals.ids),

            # include all invoices after 2022-07-01, including RC
            ('date_invoice', '>=', '2022-07-01'),
        ]
        return domain

    @api.model
    def cron_create_and_send_fatturapa_out(self, limit=10):
        invoice_model = self.env['account.invoice']
        domain = self.get_invoices_to_send_domain()
        invoices = invoice_model.search(
            domain, order='date_invoice ASC, number ASC', limit=limit)
        if invoices:
            wizard_model = self.env['wizard.export.fatturapa']
            # dummy wizard
            wizard = wizard_model.create({})

            context = self.env.context.copy()
            context['active_model'] = invoice_model._name

            ir_values_model = self.env['ir.values']
            e_invoices_to_send = self.env['fatturapa.attachment.out']
            for invoice in invoices:
                try:
                    partner = invoice.partner_id
                    if partner.electronic_invoice_subjected:
                        if not partner.codice_destinatario and not partner.ipa_code:
                            raise ValidationError(_(
                                'Electronic invoice data missing. '
                                'Check partner Electronic Invoice tab.'))

                    else:
                        if not partner.vat and not partner.fiscalcode:
                            raise ValidationError(_(
                                'Partner fiscal data missing. '
                                'Check partner Accounting tab.'))

                    # simulate invoice print to gather default report data
                    report_data = invoice.invoice_print()
                    report_model = report_data['type']
                    report = self.env[report_model].search(
                        [('report_name', '=', report_data['report_name'])])

                    # attach PDF only if a valid report is defined
                    if report:
                        wizard.report_print_menu = ir_values_model.search(
                            [('value', '=', report_model + ',' + str(report.id))])
                        wizard.generate_attach_report(invoice)

                    # clear report_print_menu field to avoid pdf regeneration
                    wizard.report_print_menu = ir_values_model

                    # export XML e-invoice for the current invoice
                    context['active_ids'] = invoice.ids
                    wizard.with_context(context).exportFatturaPA()

                    # filter public administration invoices,
                    # because they need to be signed before send
                    if not invoice.partner_id.is_pa:
                        e_invoices_to_send |= invoice.fatturapa_attachment_out_id

                except Exception as e:
                    if isinstance(e, except_orm):
                        message = e.value
                    elif isinstance(e, Exception):
                        message = e.message
                    else:
                        message = str(e)

                    invoice.fatturapa_out_error = True
                    invoice.message_post(
                        subject=_("Error during E-invoice export"),
                        body=_(message)
                    )

            # Send via PEC all e-invoices generated
            # (public administration excluded)
            if e_invoices_to_send:
                e_invoices_to_send.send_via_pec()

        return True
