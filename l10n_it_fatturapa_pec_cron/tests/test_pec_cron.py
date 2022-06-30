# -*- coding: utf-8 -*-

from openerp.addons.l10n_it_reverse_charge.tests.rc_common import ReverseChargeCommon


class TestPecCron(ReverseChargeCommon):
    def setUp(self):
        super(TestPecCron, self).setUp()

        # models
        self.account_fiscalyear_model = self.env['account.fiscalyear']
        self.fatturapa_attachment_out_model = self.env['fatturapa.attachment.out']
        self.partner_model = self.env['res.partner']

        # refs
        self.sale_journal = self.env.ref('account.sales_journal')

        # create fiscal year 2022
        self._create_fiscal_year_2022()

        self.partner_company = self.partner_model.create({
            'name': 'Test Company Partner',
            'street': 'Test Street',
            'vat': 'IT12345670017',
            'email': 'testpartner_company@mail.it',
        })

    def _create_fiscal_year_2022(self):
        fiscal_year_2022 = self.account_fiscalyear_model.search([
            ('date_start', '=', '2022-01-01'),
            ('date_stop', '=', '2022-12-31'),
        ])
        if not fiscal_year_2022:
            fiscalyear = self.env['account.fiscalyear'].create({
                'name': '2022',
                'code': '2022',
                'date_start': '2022-01-01',
                'date_stop': '2022-12-31',
                'company_id': self.company.id,
            })
            fiscalyear.create_period()
            self.assertEquals(len(fiscalyear.period_ids), 13)

    def _create_invoice(self, supplier, date_invoice, type_invoice='in_invoice'):
        journal = self.sale_journal
        if type_invoice in ['in_invoice', 'in_refund']:
            journal = self.purchases_journal

        self.supplier_intraEU.property_payment_term_id = self.term_15_30.id
        invoice = self.invoice_model.create({
            'partner_id': supplier.id,
            'account_id': self.invoice_account,
            'journal_id': journal.id,
            'type': type_invoice,
            'date_invoice': date_invoice,
        })
        res = invoice.onchange_partner_id(invoice.type, invoice.partner_id.id)
        invoice.fiscal_position = res['value']['fiscal_position']

        invoice_line_vals = {
            'name': 'Invoice for sample product',
            'account_id': self.invoice_line_account,
            'invoice_id': invoice.id,
            'product_id': self.sample_product.id,
            'price_unit': 100,
            'invoice_line_tax_id': [(4, self.tax_22ai.id, 0)]}
        invoice_line = self.invoice_line_model.create(invoice_line_vals)
        invoice_line.onchange_invoice_line_tax_id()
        self.env['account.invoice.tax'].compute(invoice)

        invoice.signal_workflow('invoice_open')
        return invoice

    def _get_invoices_to_send(self):
        domain = self.fatturapa_attachment_out_model.get_invoices_to_send_domain()
        return self.invoice_model.search(domain, order='date_invoice ASC, number ASC')

    def test_01_excluded_invoices(self):
        # Test exclusion cases
        # create invoice inv1 with fatturapa_out_error
        # create invoice inv2 in 'cancel' state
        # get invoices to send
        # expect:
        # - inv1 is not included
        # - inv2 is not included

        # create invoices
        inv1 = self._create_invoice(self.partner_company, '2022-07-01', 'out_invoice')
        inv2 = self._create_invoice(self.partner_company, '2022-07-01', 'out_invoice')
        inv1.fatturapa_out_error = True
        inv2.signal_workflow('invoice_cancel')

        # get invoices to send and check results
        invoices_ids = self._get_invoices_to_send().ids
        self.assertNotIn(inv1.id, invoices_ids)
        self.assertNotIn(inv2.id, invoices_ids)

    def test_02_sale(self):
        # Test sale invoices/refunds before and after limit date 01/07/2022
        # create invoice inv1 before limit date
        # create invoice inv2 after limit date
        # create refund ref1 before limit date
        # create refund ref2 before limit date
        # get invoices to send
        # expect:
        # - inv1 is included
        # - ref1 is included
        # - inv2 is included
        # - ref2 is included

        # create invoices before limit date
        inv1 = self._create_invoice(self.partner_company, '2022-06-01', 'out_invoice')
        ref1 = self._create_invoice(self.partner_company, '2022-06-01', 'out_refund')

        # create invoices after limit date
        inv2 = self._create_invoice(self.partner_company, '2022-07-01', 'out_invoice')
        ref2 = self._create_invoice(self.partner_company, '2022-07-01', 'out_refund')

        # get invoices to send and check results
        invoices_ids = self._get_invoices_to_send().ids
        self.assertIn(inv1.id, invoices_ids)
        self.assertIn(ref1.id, invoices_ids)
        self.assertIn(inv2.id, invoices_ids)
        self.assertIn(ref2.id, invoices_ids)

    def test_03_purchase_intra_eu(self):
        # Test IntraEU invoices/refunds before and after limit date 01/07/2022
        # create IntraEU invoice inv1 before limit date
        # create IntraEU invoice inv2 after limit date
        # create IntraEU refund ref1 before limit date
        # create IntraEU refund ref2 before limit date
        # get invoices to send
        # NB: Reverse charge self invoices generated from IntraEU invoices are
        # included or not depending on invoice date:
        # - RC invoices before 2022-07-01, should be sent via Esterometro
        # - RC invoices after 2022-07-01 have to be sent
        # expect:
        # - rc_self_invoice generated from inv1 is not included
        # - rc_self_invoice generated from ref1 is not included
        # - rc_self_invoice generated from inv2 is included
        # - rc_self_invoice generated from ref2 is included

        # create invoices before RC limit date
        inv1 = self._create_invoice(self.supplier_intraEU, '2022-06-01', 'in_invoice')
        ref1 = self._create_invoice(self.supplier_intraEU, '2022-06-01', 'in_refund')
        self.assertIsNot(bool(inv1.rc_self_invoice_id), False)
        self.assertIsNot(bool(ref1.rc_self_invoice_id), False)

        # create invoices after RC limit date
        inv2 = self._create_invoice(self.supplier_intraEU, '2022-07-01', 'in_invoice')
        ref2 = self._create_invoice(self.supplier_intraEU, '2022-07-01', 'in_refund')
        self.assertIsNot(bool(inv2.rc_self_invoice_id), False)
        self.assertIsNot(bool(ref2.rc_self_invoice_id), False)

        # get invoices to send and check results
        invoices_ids = self._get_invoices_to_send().ids
        self.assertNotIn(inv1.rc_self_invoice_id.id, invoices_ids)
        self.assertNotIn(ref1.rc_self_invoice_id.id, invoices_ids)
        self.assertIn(inv2.rc_self_invoice_id.id, invoices_ids)
        self.assertIn(ref2.rc_self_invoice_id.id, invoices_ids)
