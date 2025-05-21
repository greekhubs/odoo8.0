# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
import logging
import re # Import re for pattern matching
from datetime import datetime, date, timedelta # Added date, timedelta
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

class OllamaChatbotHistory(osv.osv):
    _name = 'ollama_chatbot.history'
    _columns = {
        'user_query': fields.text(string='User Query', required=True),
        'bot_response': fields.text(string='Bot Response'),
        'create_date': fields.datetime(string='Timestamp', readonly=True),
        'user_id': fields.many2one('res.users', string='User'),
    }
    _defaults = {
        'create_date': fields.datetime.now,
    }

    def get_sales_data(self, cr, uid, query, context=None):
        if context is None:
            context = {}
        _logger.info("Fetching sales data for query: %s by user: %s", query, uid)
        
        query_lower = query.lower().strip()
        sale_order_pool = self.pool.get('sale.order')
        partner_pool = self.pool.get('res.partner')

        # Pattern 1: "total sales last month"
        if query_lower == "total sales last month":
            _logger.info("Processing 'total sales last month' query.")
            today = datetime.today()
            first_day_current_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_last_month = first_day_current_month - relativedelta(days=1)
            first_day_last_month = last_day_last_month.replace(day=1)
            
            date_from_str = first_day_last_month.strftime('%Y-%m-%d %H:%M:%S')
            date_to_str = last_day_last_month.replace(hour=23, minute=59, second=59).strftime('%Y-%m-%d %H:%M:%S')

            _logger.info("Date range for 'last month': %s to %s", date_from_str, date_to_str)

            domain = [
                ('date_confirm', '>=', date_from_str),
                ('date_confirm', '<=', date_to_str),
                ('state', 'not in', ['draft', 'sent', 'cancel'])
            ]
            order_ids = sale_order_pool.search(cr, uid, domain, context=context)
            
            total_sales = 0.0
            if order_ids:
                orders = sale_order_pool.browse(cr, uid, order_ids, context=context)
                for order in orders:
                    total_sales += order.amount_total
                _logger.info("Found %d orders. Total sales last month: %s", len(orders), total_sales)
                return "Total sales last month: %.2f" % total_sales
            else:
                _logger.info("No sales orders found for the last month.")
                return "No sales orders found for the last month."

        # Pattern 2: "sales for customer [customer name]"
        match_customer = re.match(r"sales for customer (.*)", query_lower)
        if match_customer:
            customer_name = match_customer.group(1).strip()
            _logger.info("Processing 'sales for customer' query for customer: %s", customer_name)
            
            partner_ids = partner_pool.search(cr, uid, [('name', 'ilike', customer_name)], context=context)
            if not partner_ids:
                _logger.info("Customer '%s' not found.", customer_name)
                return "Customer '%s' not found." % customer_name
            
            partner_id = partner_ids[0]
            domain = [('partner_id', '=', partner_id), ('state', 'not in', ['draft', 'sent', 'cancel'])]
            order_ids = sale_order_pool.search(cr, uid, domain, context=context)
            
            if not order_ids:
                _logger.info("No confirmed sales orders found for customer '%s'.", customer_name)
                return "No confirmed sales orders found for customer '%s'." % customer_name
            
            orders = sale_order_pool.browse(cr, uid, order_ids, context=context)
            result_orders = []
            for order in orders:
                result_orders.append({'name': order.name, 'date_confirm': order.date_confirm, 'amount_total': order.amount_total})
            
            if len(result_orders) > 5:
                _logger.info("Found %d orders for customer '%s'. Returning summary.", len(result_orders), customer_name)
                return "Found %d orders for customer '%s'. First 5 are: %s. Total amount: %.2f" % (
                    len(result_orders), customer_name, str([o['name'] for o in result_orders[:5]]), sum(o['amount_total'] for o in result_orders))
            _logger.info("Found %d orders for customer '%s': %s", len(result_orders), customer_name, result_orders)
            return result_orders

        # Pattern 3: "details of order [order number]"
        match_order = re.match(r"details of order (.*)", query_lower)
        if match_order:
            order_name = match_order.group(1).strip()
            _logger.info("Processing 'details of order' query for order: %s", order_name)
            domain = [('name', '=', order_name)]
            order_ids = sale_order_pool.search(cr, uid, domain, context=context)
            
            if not order_ids:
                _logger.info("Order '%s' not found.", order_name)
                return "Order '%s' not found." % order_name
            
            order = sale_order_pool.browse(cr, uid, order_ids[0], context=context)
            order_lines = []
            for line in order.order_line:
                order_lines.append({
                    'product': line.product_id.name_template if line.product_id else 'N/A',
                    'quantity': line.product_uom_qty, 'price_unit': line.price_unit, 'subtotal': line.price_subtotal})
            result = {'name': order.name, 'partner_id': order.partner_id.name if order.partner_id else 'N/A',
                      'date_confirm': order.date_confirm, 'amount_total': order.amount_total, 'state': order.state, 'lines': order_lines}
            _logger.info("Details for order '%s': %s", order_name, result)
            return result

        _logger.info("Query '%s' did not match any known sales data patterns.", query)
        return "Sorry, I can only answer about 'total sales last month', 'sales for customer [name]', or 'details of order [number]' for now."

    def get_attendance_data(self, cr, uid, query, context=None):
        if context is None:
            context = {}
        _logger.info("Fetching attendance data for query: %s by user: %s", query, uid)

        query_lower = query.lower().strip()
        attendance_pool = self.pool.get('hr.attendance')
        employee_pool = self.pool.get('hr.employee')

        # Pattern 1: "who was present yesterday?"
        if query_lower == "who was present yesterday?":
            _logger.info("Processing 'who was present yesterday?' query.")
            yesterday_date_obj = date.today() - timedelta(days=1)
            yesterday_start_str = datetime(yesterday_date_obj.year, yesterday_date_obj.month, yesterday_date_obj.day, 0, 0, 0).strftime('%Y-%m-%d %H:%M:%S')
            yesterday_end_str = datetime(yesterday_date_obj.year, yesterday_date_obj.month, yesterday_date_obj.day, 23, 59, 59).strftime('%Y-%m-%d %H:%M:%S')
            _logger.info("Date range for 'yesterday': %s to %s", yesterday_start_str, yesterday_end_str)

            domain = [('name', '>=', yesterday_start_str), ('name', '<=', yesterday_end_str)]
            attendance_ids = attendance_pool.search(cr, uid, domain, context=context)
            
            if not attendance_ids:
                _logger.info("No attendance records found for yesterday.")
                return "No attendance records found for yesterday."

            attendances = attendance_pool.browse(cr, uid, attendance_ids, context=context)
            present_employee_ids = list(set([att.employee_id.id for att in attendances if att.employee_id]))
            
            if not present_employee_ids:
                _logger.info("No employees found from attendance records for yesterday.")
                return "No employees were recorded as present yesterday."

            present_employees = employee_pool.browse(cr, uid, present_employee_ids, context=context)
            employee_names = [employee.name for employee in present_employees]
            
            _logger.info("Employees present yesterday: %s", employee_names)
            return employee_names

        # Pattern 2: "attendance for employee [employee name] on [YYYY-MM-DD]"
        match_employee_date = re.match(r"attendance for employee (.*) on (\d{4}-\d{2}-\d{2})", query_lower)
        if match_employee_date:
            employee_name = match_employee_date.group(1).strip()
            date_str = match_employee_date.group(2).strip()
            _logger.info("Processing 'attendance for employee on date' query for: %s on %s", employee_name, date_str)

            try:
                target_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                _logger.warning("Invalid date format: %s", date_str)
                return "Invalid date format. Please use YYYY-MM-DD."

            date_start_str = datetime(target_date_obj.year, target_date_obj.month, target_date_obj.day, 0, 0, 0).strftime('%Y-%m-%d %H:%M:%S')
            date_end_str = datetime(target_date_obj.year, target_date_obj.month, target_date_obj.day, 23, 59, 59).strftime('%Y-%m-%d %H:%M:%S')
            
            employee_ids = employee_pool.search(cr, uid, [('name', 'ilike', employee_name)], context=context)
            if not employee_ids:
                _logger.info("Employee '%s' not found.", employee_name)
                return "Employee '%s' not found." % employee_name
            
            emp_id = employee_ids[0]
            employee_actual_name = employee_pool.browse(cr, uid, emp_id, context=context).name

            domain = [('employee_id', '=', emp_id), ('name', '>=', date_start_str), ('name', '<=', date_end_str)]
            attendance_ids = attendance_pool.search(cr, uid, domain, order='name asc', context=context)

            if not attendance_ids:
                _logger.info("No attendance records found for '%s' on %s.", employee_actual_name, date_str)
                return "No attendance records found for '%s' on %s." % (employee_actual_name, date_str)
            
            attendances = attendance_pool.browse(cr, uid, attendance_ids, context=context)
            result_records = []
            for rec in attendances:
                result_records.append({'name': rec.name, 'action': rec.action, 'employee': rec.employee_id.name})
            _logger.info("Found %d attendance records for '%s' on %s: %s", len(result_records), employee_actual_name, date_str, result_records)
            return result_records

        # Pattern 3: "attendance for employee [employee name] yesterday"
        match_employee_yesterday = re.match(r"attendance for employee (.*) yesterday", query_lower)
        if match_employee_yesterday:
            employee_name = match_employee_yesterday.group(1).strip()
            _logger.info("Processing 'attendance for employee yesterday' query for: %s", employee_name)

            yesterday_date_obj = date.today() - timedelta(days=1)
            date_start_str = datetime(yesterday_date_obj.year, yesterday_date_obj.month, yesterday_date_obj.day, 0, 0, 0).strftime('%Y-%m-%d %H:%M:%S')
            date_end_str = datetime(yesterday_date_obj.year, yesterday_date_obj.month, yesterday_date_obj.day, 23, 59, 59).strftime('%Y-%m-%d %H:%M:%S')

            employee_ids = employee_pool.search(cr, uid, [('name', 'ilike', employee_name)], context=context)
            if not employee_ids:
                _logger.info("Employee '%s' not found.", employee_name)
                return "Employee '%s' not found." % employee_name

            emp_id = employee_ids[0]
            employee_actual_name = employee_pool.browse(cr, uid, emp_id, context=context).name

            domain = [('employee_id', '=', emp_id), ('name', '>=', date_start_str), ('name', '<=', date_end_str)]
            attendance_ids = attendance_pool.search(cr, uid, domain, order='name asc', context=context)

            if not attendance_ids:
                _logger.info("No attendance records found for '%s' yesterday.", employee_actual_name)
                return "No attendance records found for '%s' yesterday." % employee_actual_name
            
            attendances = attendance_pool.browse(cr, uid, attendance_ids, context=context)
            result_records = []
            for rec in attendances:
                result_records.append({'name': rec.name, 'action': rec.action, 'employee': rec.employee_id.name})
            _logger.info("Found %d attendance records for '%s' yesterday: %s", len(result_records), employee_actual_name, result_records)
            return result_records

        _logger.info("Query '%s' did not match any known attendance data patterns.", query)
        return "Sorry, I can only answer about 'who was present yesterday?' or 'attendance for employee [name] on [date]/yesterday' for now."

    def get_bank_statement_data(self, cr, uid, query, context=None):
        if context is None:
            context = {}
        _logger.info("Fetching bank statement data for query: %s by user: %s", query, uid)

        query_lower = query.lower().strip()
        journal_pool = self.pool.get('account.journal')
        statement_pool = self.pool.get('account.bank.statement')
        # statement_line_pool = self.pool.get('account.bank.statement.line') # Not directly used for search

        # Helper to find journal
        def find_journal(journal_name_query):
            journal_ids = journal_pool.search(cr, uid, [
                ('name', 'ilike', journal_name_query),
                ('type', 'in', ['bank', 'cash'])
            ], context=context)
            if not journal_ids:
                _logger.info("Journal '%s' not found or is not a bank/cash journal.", journal_name_query)
                return None, "Journal '%s' not found or is not a bank/cash journal." % journal_name_query
            # Assuming first match is the correct one
            journal = journal_pool.browse(cr, uid, journal_ids[0], context=context)
            return journal, None

        # Pattern 1: "balance for journal [journal name]"
        match_balance = re.match(r"balance for journal (.*)", query_lower)
        if match_balance:
            journal_name = match_balance.group(1).strip()
            _logger.info("Processing 'balance for journal' query for journal: %s", journal_name)

            journal, error_msg = find_journal(journal_name)
            if error_msg:
                return error_msg
            
            statement_ids = statement_pool.search(cr, uid, [('journal_id', '=', journal.id)],
                                                  order='date desc, id desc', limit=1, context=context)
            if not statement_ids:
                _logger.info("No bank statements found for journal '%s'.", journal.name)
                return "No bank statements found for journal '%s'." % journal.name
            
            statement = statement_pool.browse(cr, uid, statement_ids[0], context=context)
            result = "Ending balance for journal '%s' on %s is %.2f" % (journal.name, statement.date, statement.balance_end_real)
            _logger.info(result)
            return result

        # Helper function for fetching transactions
        def get_transactions_for_date(journal_name_query, date_obj):
            journal, error_msg = find_journal(journal_name_query)
            if error_msg:
                return error_msg

            date_str_search = date_obj.strftime('%Y-%m-%d') # Odoo date fields are stored as YYYY-MM-DD strings
            _logger.info("Searching transactions for journal '%s' on date: %s", journal.name, date_str_search)

            statement_ids = statement_pool.search(cr, uid, [
                ('journal_id', '=', journal.id),
                ('date', '=', date_str_search) # Direct comparison for date fields
            ], context=context)

            if not statement_ids:
                _logger.info("No bank statements found for journal '%s' on %s.", journal.name, date_str_search)
                return "No bank statements found for journal '%s' on %s." % (journal.name, date_str_search)

            all_transactions = []
            statements = statement_pool.browse(cr, uid, statement_ids, context=context)
            for stmt in statements:
                if not stmt.line_ids:
                    _logger.info("Statement '%s' has no transaction lines.", stmt.name)
                    continue
                for line in stmt.line_ids:
                    all_transactions.append({
                        'statement': stmt.name,
                        'date': line.date,
                        'name': line.name,
                        'partner': line.partner_id.name if line.partner_id else '',
                        'amount': line.amount
                    })
            
            if not all_transactions:
                _logger.info("No transaction lines found for journal '%s' on %s across %d statements.", journal.name, date_str_search, len(statements))
                return "No transaction lines found for journal '%s' on %s." % (journal.name, date_str_search)
            
            _logger.info("Found %d transactions for journal '%s' on %s.", len(all_transactions), journal.name, date_str_search)
            return all_transactions

        # Pattern 2: "transactions on date [YYYY-MM-DD] for journal [journal name]"
        match_trans_date = re.match(r"transactions on date (\d{4}-\d{2}-\d{2}) for journal (.*)", query_lower)
        if match_trans_date:
            date_str = match_trans_date.group(1).strip()
            journal_name = match_trans_date.group(2).strip()
            _logger.info("Processing 'transactions on date' query for journal: %s on %s", journal_name, date_str)
            try:
                target_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                _logger.warning("Invalid date format for transactions: %s", date_str)
                return "Invalid date format. Please use YYYY-MM-DD."
            return get_transactions_for_date(journal_name, target_date_obj)

        # Pattern 3: "transactions yesterday for journal [journal name]"
        match_trans_yesterday = re.match(r"transactions yesterday for journal (.*)", query_lower)
        if match_trans_yesterday:
            journal_name = match_trans_yesterday.group(1).strip()
            _logger.info("Processing 'transactions yesterday' query for journal: %s", journal_name)
            yesterday_date_obj = date.today() - timedelta(days=1)
            return get_transactions_for_date(journal_name, yesterday_date_obj)

        _logger.info("Query '%s' did not match any known bank statement data patterns.", query)
        return "Sorry, I can only answer about 'balance for journal [name]' or 'transactions on [date]/yesterday for journal [name]' for now."
