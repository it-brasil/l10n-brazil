# -*- encoding: utf-8 -*-
###############################################################################
#                                                                             #
# Copyright (C) 2009  Renato Lima - Akretion, Gabriel C. Stabel               #
# Copyright (C) 2012  Raphaël Valyi - Akretion                                #
#                                                                             #
#This program is free software: you can redistribute it and/or modify         #
#it under the terms of the GNU Affero General Public License as published by  #
#the Free Software Foundation, either version 3 of the License, or            #
#(at your option) any later version.                                          #
#                                                                             #
#This program is distributed in the hope that it will be useful,              #
#but WITHOUT ANY WARRANTY; without even the implied warranty of               #
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the                #
#GNU Affero General Public License for more details.                          #
#                                                                             #
#You should have received a copy of the GNU Affero General Public License     #
#along with this program.  If not, see <http://www.gnu.org/licenses/>.        #
###############################################################################

from osv import osv, fields
from tools.translate import _
import decimal_precision as dp


class purchase_order(osv.osv):
    _inherit = 'purchase.order'

    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        cur_obj = self.pool.get('res.currency')
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }
            val = val1 = 0.0
            cur = order.pricelist_id.currency_id
            for line in order.order_line:
                val1 += line.price_subtotal
                for c in self.pool.get('account.tax').compute_all(
                    cr, uid, line.taxes_id, line.price_unit, line.product_qty,
                    order.partner_address_id.id, line.product_id.id,
                    order.partner_id)['taxes']:
                    
                    tax_brw = self.pool.get('account.tax').browse(cr, uid, c['id'])
                    if not tax_brw.tax_code_id.tax_discount:
                        val += c.get('amount', 0.0)
            res[order.id]['amount_tax'] = cur_obj.round(cr, uid, cur, val)
            res[order.id]['amount_untaxed'] = cur_obj.round(cr, uid, cur, val1)
            res[order.id]['amount_total'] = res[order.id]['amount_untaxed'] + res[order.id]['amount_tax']
        return res

    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('purchase.order.line').browse(
            cr, uid, ids, context=context):
            result[line.order_id.id] = True
        return result.keys()

    def _default_fiscal_category(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        return user.company_id.purchase_fiscal_category_id and user.company_id.purchase_fiscal_category_id.id or False

    _columns = {
        'fiscal_category_id': fields.many2one(
            'l10n_br_account.fiscal.category', 'Categoria Fiscal',
            domain="[('type', '=', 'input'), \
            ('journal_type', '=', 'purchase')]"),
        'amount_untaxed': fields.function(
            _amount_all, method=True,
            digits_compute=dp.get_precision('Purchase Price'),
            string='Untaxed Amount',
            store={'purchase.order.line': (_get_order, None, 10)},
            multi="sums", help="The amount without tax"),
        'amount_tax': fields.function(
            _amount_all, method=True,
            digits_compute=dp.get_precision('Purchase Price'), string='Taxes',
            store={'purchase.order.line': (_get_order, None, 10)},
            multi="sums", help="The tax amount"),
        'amount_total': fields.function(
            _amount_all, method=True,
            digits_compute=dp.get_precision('Purchase Price'), string='Total',
            store={'purchase.order.line': (_get_order, None, 10)},
            multi="sums", help="The total amount")}

    _defaults = {
        'fiscal_category_id': _default_fiscal_category}

    def _fiscal_position_map(self, cr, uid, ids, partner_id,
                             partner_invoice_id, company_id,
                             fiscal_category_id):
        
        obj_fp_rule = self.pool.get('account.fiscal.position.rule')
        result = obj_fp_rule.fiscal_position_map(
            cr, uid, partner_id, partner_invoice_id, company_id,
            fiscal_category_id,
            context={'use_domain': ('use_purchase', '=', True)})
        return result

    def onchange_partner_id(self, cr, uid, ids, partner_id=False,
                            partner_address_id=False, company_id=False,
                            fiscal_category_id=False):
        result = super(purchase_order, self).onchange_partner_id(
            cr, uid, ids, partner_id, company_id)
        if result['value']['partner_address_id']:
            partner_address_id = result['value']['partner_address_id']
        fiscal_data = self._fiscal_position_map(
            cr, uid, ids, partner_id, partner_address_id, company_id,
            fiscal_category_id)
        result['value'].update(fiscal_data)
        return result

    def onchange_partner_address_id(self, cr, uid, ids, partner_id=False,
                                    partner_address_id=False, company_id=False,
                                    fiscal_category_id=False):

        result = super(purchase_order, self).onchange_partner_address_id(
            cr, uid, ids, partner_address_id, company_id)

        fiscal_data = self._fiscal_position_map(
            cr, uid, ids, partner_id, partner_address_id, company_id,
            fiscal_category_id)
        result['value'].update(fiscal_data)
        return result

    def onchange_fiscal_category_id(self, cr, uid, ids,
                                    partner_id=False, partner_address_id=False,
                                    company_id=False,
                                    fiscal_category_id=False, context=None):
        result = {'value': {}}
        fiscal_data = self._fiscal_position_map(
            cr, uid, ids, partner_id, partner_address_id, company_id,
            fiscal_category_id)
        result['value'].update(fiscal_data)
        return result

    def _prepare_inv_line(self, cr, uid, account_id, order_line, context=None):
        
        result = super(purchase_order, self)._prepare_inv_line(
            cr, uid, account_id, order_line, context)
        
        order = order_line.order_id
        
        result['fiscal_category_id'] = order_line.fiscal_category_id and \
        order_line.fiscal_category_id.id or order.fiscal_category_id and \
        order.fiscal_category_id.id
        
        result['fiscal_position'] = order_line.fiscal_position and \
        order_line.fiscal_position.id or order.fiscal_position and \
        order.fiscal_position.id
        
        result['cfop_id'] = order.fiscal_position and \
        order.fiscal_position.cfop_id and order.fiscal_position.cfop_id.id or \
        order.fiscal_position and order.fiscal_position.cfop_id and \
        order.fiscal_position.cfop_id.id
        
        return result

    # TODO ask OpenERP SA for a _prepare_invoice method!
    def action_invoice_create(self, cr, uid, ids, *args):
        inv_id = super(purchase_order, self).action_invoice_create(cr, uid,
                                                                   ids, *args)
        for order in self.browse(cr, uid, ids):
            # REMARK: super method is ugly as it assumes only one invoice
            # for possibly several purchase orders.
            if inv_id:
                company_id = order.company_id
                if not company_id.document_serie_product_ids:
                    raise osv.except_osv(
                        _('No fiscal document serie found!'),
                        _("No fiscal document serie found for selected \
                        company %s") % (order.company_id.name))
                
                journal_id = order.fiscal_category_id and \
                order.fiscal_category_id.property_journal.id or False
                
                if not journal_id:
                    raise osv.except_osv(
                        _(u'Nenhuma Diário!'),
                        _(u"Categoria de operação fisca: '%s', não tem um \
                        diário contábil para a empresa %s") % (
                            order.fiscal_category_id.name,
                            order.company_id.name))

                comment = ''
                if order.fiscal_position.inv_copy_note:
                    comment = order.fiscal_position.note or ''
                if order.notes:
                    comment += ' - ' + order.notes

                self.pool.get('account.invoice').write(cr, uid, inv_id, {
                     'fiscal_category_id': order.fiscal_category_id and order.fiscal_category_id.id,
                     'fiscal_position': order.fiscal_position and order.fiscal_position.id,
                     'own_invoice': False,
                     'comment': comment,
                     'journal_id': journal_id})
        return inv_id

    def action_picking_create(self, cr, uid, ids, *args):
        picking_id = False
        for order in self.browse(cr, uid, ids):
            picking_id = super(purchase_order, self).action_picking_create(
                cr, uid, ids, *args)
            self.pool.get('stock.picking').write(
                cr, uid, picking_id, 
                {'fiscal_category_id': order.fiscal_category_id.id,
                 'fiscal_position': order.fiscal_position.id})
        return picking_id

purchase_order()


class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'
    _columns = {
        'fiscal_category_id': fields.many2one(
            'l10n_br_account.fiscal.category', 'Categoria Fiscal',
            domain="[('type', '=', 'input'), \
            ('journal_type', '=', 'purchase')]"),
        'fiscal_position': fields.many2one(
            'account.fiscal.position', u'Posição Fiscal',
            domain="[('fiscal_category_id', '=', fiscal_category_id)]")}

    def _fiscal_position_map(self, cr, uid, partner_id, partner_address_id,
                             company_id, fiscal_category_id, product_id=False,
                             context=None):
        
        if context is None: context = {}
        obj_fp_rule = self.pool.get('account.fiscal.position.rule')
        fiscal_result = obj_fp_rule.fiscal_position_map(
            cr, uid, partner_id, partner_address_id, company_id,
            fiscal_category_id,
            context=context)
        if product_id and fiscal_result.get('fiscal_position', False):
            obj_fposition = self.pool.get('account.fiscal.position').browse(
                cr, uid, fiscal_result['fiscal_position'])
            obj_product = self.pool.get('product.product').browse(
                cr, uid, product_id)
            context.update({'fiscal_type': obj_product.fiscal_type,
                            'type_tax_use': 'purchase'})
            taxes = obj_product.supplier_taxes_id or False
            tax_ids = self.pool.get('account.fiscal.position').map_tax(
                cr, uid, obj_fposition, taxes, context)

            fiscal_result['taxes_id'] = tax_ids

        return fiscal_result

    def product_id_change(self, cr, uid, ids, pricelist_id, product_id, qty,
                          uom_id, partner_id, date_order=False,
                          fiscal_position_id=False, date_planned=False,
                          name=False, price_unit=False, notes=False,
                          context=None, fiscal_category_id=False,
                          partner_address_id=False, company_id=False):
        print context
        if context is None: context = {}
        if product_id:
            obj_product = self.pool.get('product.product').browse(
                cr, uid, product_id)
            context.update({'fiscal_type': obj_product.fiscal_type,
                            'type_tax_use': 'purchase'})
        
        result = super(purchase_order_line, self).product_id_change(
            cr, uid, ids, pricelist_id, product_id, qty, uom_id, partner_id,
            date_order, fiscal_position_id, date_planned, name, price_unit,
            notes, context)

        if not product_id or not fiscal_category_id:
            return result
        
        obj_fp_rule = self.pool.get('account.fiscal.position.rule')
        product_fiscal_category_id = obj_fp_rule.product_fiscal_category_map(
            cr, uid, product_id, fiscal_category_id)

        result['value']['fiscal_category_id'] = product_fiscal_category_id or \
        fiscal_category_id

        fiscal_result = self._fiscal_position_map(
            cr, uid, partner_id, partner_address_id, company_id,
            result['value']['fiscal_category_id'], product_id,
            context={'use_domain': ('use_purchase', '=', True)})
        result['value'].update(fiscal_result)
        return result

    def onchange_fiscal_category_id(self, cr, uid, ids, partner_id,
                                        partner_address_id=False,
                                        product_id=False,
                                        fiscal_category_id=False,
                                        company_id=False, context=None):

        result = {'value': {}}
        if not company_id or not partner_id:
            return result

        fiscal_result = self._fiscal_position_map(
            cr, uid, partner_id, partner_address_id, company_id,
            fiscal_category_id, product_id,
            context={'use_domain': ('use_purchase', '=', True)})

        result['value'].update(fiscal_result)
        return result    
    
    def onchange_fiscal_position(self, cr, uid, ids, partner_id,
                                 partner_address_id=False, product_id=False,
                                 fiscal_position=False,
                                 fiscal_category_id=False, company_id=False,
                                 context=None):
        result = {'value': {}}
        if not company_id or not partner_id or not fiscal_position:
            return result

        fiscal_result = self._fiscal_position_map(
            cr, uid, partner_id, partner_address_id, company_id,
            fiscal_category_id, product_id,
            context={'use_domain': ('use_purchase', '=', True)})
        
        result['value'].update(fiscal_result)
        return result

purchase_order_line()
