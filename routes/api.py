from flask import jsonify, session
from mysql.connector import Error
from db import get_db_connection

def register_api_routes(app):
    @app.route('/api/get_restock_order/<int:order_no>')
    def api_get_restock_order(order_no):
        """Returns full restock order details: header + itemised line items."""
        if 'staff_id' not in session:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'DB error'}), 500
        try:
            cur = conn.cursor(dictionary=True)
            # Query 1 (Master)
            cur.execute("""
                SELECT ro.Order_No, ro.OrderDate, ro.OrderCost, 
                       s.Name AS Supplier_Name, st.Name AS Staff_Name 
                FROM RESTOCK_ORDER ro 
                JOIN SUPPLIER s ON ro.Company_ID = s.Company_ID 
                JOIN STAFF st ON ro.Staff_ID = st.Staff_ID 
                WHERE ro.Order_No = %s
            """, (order_no,))
            master_data = cur.fetchone()
            
            if not master_data:
                return jsonify({'status': 'error', 'message': 'Order not found or server error'}), 404
                
            # Serialise date
            if master_data.get('OrderDate'):
                master_data['OrderDate'] = str(master_data['OrderDate'])
            master_data['OrderCost'] = float(master_data.get('OrderCost') or 0)
            
            # Query 2 (Items)
            cur.execute("""
                SELECT d.Name AS Medicine, ri.Qty_Ordered, ri.Unit_Cost, 
                       (ri.Qty_Ordered * ri.Unit_Cost) AS Subtotal 
                FROM RESTOCK_ITEMS ri 
                JOIN DRUG d ON ri.Barcode = d.Barcode 
                WHERE ri.Order_No = %s
            """, (order_no,))
            items_data = cur.fetchall()
            for it in items_data:
                it['Unit_Cost'] = float(it['Unit_Cost'])
                it['Subtotal']  = float(it['Subtotal'])
                
            return jsonify({'status': 'success', 'master': master_data, 'items': items_data})
        except Error as e:
            return jsonify({'status': 'error', 'message': 'Order not found or server error'}), 404
        finally:
            if conn.is_connected(): cur.close(); conn.close()

    @app.route('/api/lookup_customer/<phone_number>')
    def api_lookup_customer(phone_number):
        """Fast lookup: does this phone number belong to an existing customer?"""
        if 'staff_id' not in session:
            return jsonify({'found': False}), 403
        conn = get_db_connection()
        if not conn:
            return jsonify({'found': False}), 500
        try:
            cur = conn.cursor()
            cur.execute("SELECT Name FROM CUSTOMER WHERE PhnNo = %s", (phone_number,))
            result = cur.fetchone()
            if result:
                return jsonify({'found': True, 'name': result[0]})
            return jsonify({'found': False})
        except Error as e:
            return jsonify({'found': False, 'error': str(e)}), 500
        finally:
            if conn.is_connected(): cur.close(); conn.close()

    @app.route('/api/get_bill/<bill_no>')
    def api_get_bill(bill_no):
        """Returns full bill detail: items, customer info (from CUSTOMER table), staff name."""
        if 'staff_id' not in session:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'DB error'}), 500
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT cb.Bill_No, cb.SaleDate, cb.Total_Amount,
                       c.Name   AS Customer_Name,
                       c.PhnNo  AS Customer_Phone,
                       s.Name   AS Staff_Name
                FROM CUSTOMER_BILL cb
                LEFT JOIN STAFF    s ON cb.Staff_ID    = s.Staff_ID
                LEFT JOIN CUSTOMER c ON cb.Customer_ID = c.Customer_ID
                WHERE cb.Bill_No = %s
            """, (bill_no,))
            bill = cur.fetchone()
            if not bill:
                return jsonify({'success': False, 'error': 'Bill not found'}), 404
            # Line items
            cur.execute("""
                SELECT bi.BatchNo, bi.Barcode, d.Name AS drug_name,
                       bi.Qty_Sold, b.Unit_Selling_Price,
                       (bi.Qty_Sold * b.Unit_Selling_Price) AS line_total
                FROM BILL_ITEMS bi
                JOIN INVENTORY_BATCH b ON bi.BatchNo = b.BatchNo AND bi.Barcode = b.Barcode
                JOIN DRUG d ON b.Barcode = d.Barcode
                WHERE bi.Bill_No = %s
            """, (bill_no,))
            items = cur.fetchall()
            # Convert date to ISO string for JSON
            if bill.get('SaleDate'):
                bill['SaleDate'] = str(bill['SaleDate'])
            # Convert Decimal to float for JSON
            for it in items:
                it['Unit_Selling_Price'] = float(it['Unit_Selling_Price'])
                it['line_total']         = float(it['line_total'])
            return jsonify({'success': True, 'bill': bill, 'items': items})
        except Error as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn.is_connected(): conn.close()
