
# -*- encoding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################


from openerp.osv import osv
from openerp.tools.translate import _


# Wizard que permite conciliar los Vales de combustible en una factura
class tms_fuelvoucher_invoice(osv.osv_memory):

    """ To create invoice for each Fuel Voucher"""

    _name = 'tms.fuelvoucher.invoice'
    _description = 'Make Invoices from Fuel Vouchers'

    def makeInvoices(self, cr, uid, ids, context=None):
        """
             To get Fuel Voucher and create Invoice
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """
        if context is None:
            context={}
        record_ids =  context.get('active_ids',[])
        if record_ids:
            res = False
            invoices = []
            property_obj=self.pool.get('ir.property')
            partner_obj=self.pool.get('res.partner')
            account_fiscal_obj=self.pool.get('account.fiscal.position')
            invoice_line_obj=self.pool.get('account.invoice.line')
            account_jrnl_obj=self.pool.get('account.journal')
            invoice_obj=self.pool.get('account.invoice')
            fuelvoucher_obj=self.pool.get('tms.fuelvoucher')
            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'purchase'),('tms_expense_suppliers_journal', '=', 1)], context=None)
            journal_id = journal_id and journal_id[0] or False
            cr.execute("select distinct partner_id, currency_id from tms_fuelvoucher where (invoice_id is null or invoice_id=(select ai.id from account_invoice ai where ai.id=invoice_id and state = 'cancel')) and state in ('confirmed', 'closed') and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv(_('Warning !'),
                                 _('Selected records are not Confirmed or already invoiced...'))
            #print data_ids
            for data in data_ids:
                partner = partner_obj.browse(cr,uid,data[0])
                cr.execute("select id from tms_fuelvoucher where (invoice_id is null or invoice_id=(select ai.id from account_invoice ai where ai.id=invoice_id and state = 'cancel')) and state in ('confirmed', 'closed') and partner_id=" + str(data[0]) + ' and currency_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                fuelvoucher_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                inv_lines = []
                notes = "Conciliacion de Vales de Combustible. "
                for line in fuelvoucher_obj.browse(cr,uid,fuelvoucher_ids):
                    if (not line.invoiced) and (line.state not in ('draft','approved','cancel')):                      
                        if line.product_id:
                            a = line.product_id.product_tmpl_id.property_account_expense.id
                            if not a:
                                a = line.product_id.categ_id.property_account_expense_categ.id
                            if not a:
                                raise osv.except_osv(_('Error !'),
                                        _('There is no expense account defined ' \
                                                'for this product: "%s" (id:%d)') % \
                                                (line.product_id.name, line.product_id.id,))
                        else:
                            a = property_obj.get(cr, uid,
                                    'property_account_expense_categ', 'product.category',
                                    context=context).id
                    a = account_fiscal_obj.map_account(cr, uid, False, a)
                    #print "line.price_unit: ", line.price_unit
                    inv_line = (0,0, {
                        'name': line.product_id.name + ' - ' + (line.travel_id and line.travel_id.name or ' ') + ' - ' + line.name,
                        'origin': line.name,
                        'account_id': a,
                        'price_unit': line.price_unit,
                        'quantity': line.product_uom_qty,
                        'uos_id': line.product_uom.id,
                        'product_id': line.product_id.id,
                        'invoice_line_tax_id': [(6, 0, [x.id for x in line.product_id.supplier_taxes_id])],
                        'note': line.notes,
                        'account_analytic_id': False,
                        'vehicle_id'    : line.unit_id.id,
                        'employee_id'   : line.employee_id and line.employee_id.id or False,
                        'sale_shop_id'  : line.shop_id.id,
                        })
                    #print "inv_line: ", inv_line
                    inv_lines.append(inv_line)
                    notes += '\n' + line.name
                a = partner.property_account_payable.id
                if partner and partner.property_payment_term.id:
                    pay_term = partner.property_payment_term.id
                else:
                    pay_term = False
                inv = {
                    'name'              : _('Fuel Vouchers Invoice'),
                    'origin'            : _('Invoice from Fuel Vouchers'),
                    'type'              : 'in_invoice',
                    'journal_id'        : journal_id,
                    'reference'         : _('Fuel Vouchers Invoice'),
                    'account_id'        : a,
                    'partner_id'        : partner.id,
                    #'address_invoice_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    #'address_contact_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'invoice_line'      : [x for x in inv_lines],
                    'currency_id'       : data[1],
                    'comment'           : 'TMS-Conciliacion de Vales de Combustible',
                    'payment_term'      : pay_term,
                    'fiscal_position'   : partner.property_account_position.id,
                    'comment'           : notes,
                }
                inv_id = invoice_obj.create(cr, uid, inv)
                invoices.append(inv_id)
                fuelvoucher_obj.write(cr,uid,fuelvoucher_ids, {'invoice_id': inv_id})               
        return {
            'domain': "[('id','in', ["+','.join(map(str,invoices))+"])]",
            'name': _('Supplier Invoices'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'in_invoice', 'journal_type': 'purchase'}",
            'type': 'ir.actions.act_window'
        }
