from flask import render_template, request, redirect, url_for, session, flash, jsonify
from mysql.connector import Error
from db import get_db_connection, require_role, resolve_sort, resolve_order

PHARM_SORT = {
    'Name':    'd.Name',
    'price':   'b.Unit_Selling_Price',
    'qty':     'b.Qty_In_Stock',
    'BatchNo': 'b.BatchNo',
}

def register_pharmacist_routes(app):
    @app.route('/pharmacist')
    def pharmacist():
        if not require_role('Pharmacist'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))

        sort = request.args.get('sort', 'Name')
        order= resolve_order(request.args.get('order', 'ASC'))
        
        order_col = resolve_sort(sort, PHARM_SORT, 'Name')

        staff_id = session.get('staff_id')
        conn = get_db_connection()
        medicines = []
        my_bills = []; my_total_sales = 0.0; my_total_bills = 0
        if conn:
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute(f"""
                    SELECT b.BatchNo, b.Barcode, d.Name,
                           b.Qty_In_Stock, b.Unit_Selling_Price
                    FROM INVENTORY_BATCH b
                    JOIN DRUG d ON b.Barcode = d.Barcode
                    WHERE b.Qty_In_Stock > 0
                    ORDER BY {order_col} {order}
                """)
                medicines = cur.fetchall()

                # ── Personal sales history ──────────────────────────────────────
                cur.execute("""
                    SELECT b.Bill_No, b.SaleDate, b.Total_Amount,
                           c.Name AS Customer_Name
                    FROM CUSTOMER_BILL b
                    JOIN CUSTOMER c ON b.Customer_ID = c.Customer_ID
                    WHERE b.Staff_ID = %s
                    ORDER BY b.SaleDate DESC
                """, (staff_id,))
                my_bills = cur.fetchall()

                cur.execute(
                    "SELECT SUM(Total_Amount) AS rev FROM CUSTOMER_BILL WHERE Staff_ID = %s",
                    (staff_id,)
                )
                row = cur.fetchone()
                my_total_sales = float(row['rev'] or 0)

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM CUSTOMER_BILL WHERE Staff_ID = %s",
                    (staff_id,)
                )
                my_total_bills = int(cur.fetchone()['cnt'] or 0)

            except Error as e:
                print(f"[PHARMACIST FETCH ERROR] {e}")
                flash('Could not load medicines.', 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()

        return render_template('pharmacist.html',
                               name=session.get('name'),
                               medicines=medicines, sort=sort, order=order,
                               my_bills=my_bills,
                               my_total_sales=my_total_sales,
                               my_total_bills=my_total_bills)

    @app.route('/pharmacist/checkout', methods=['POST'])
    def pharmacist_checkout():
        if not require_role('Pharmacist'):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        data           = request.get_json()
        cart           = data.get('cart', [])
        customer_name  = data.get('customer_name', '').strip()
        customer_phone = data.get('customer_phone', '').strip()
        staff_id       = session.get('staff_id')

        if not cart:
            return jsonify({'success': False, 'error': 'Cart is empty'}), 400
        if not customer_name:
            return jsonify({'success': False, 'error': 'Customer Name is required'}), 400
        if not customer_phone:
            return jsonify({'success': False, 'error': 'Customer Phone is required'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        try:
            cur = conn.cursor(dictionary=True)

            # ── Step 1: Look up or create customer ──────────────────────────────
            cur.execute("SELECT Customer_ID FROM CUSTOMER WHERE PhnNo = %s", (customer_phone,))
            existing = cur.fetchone()
            if existing:
                cust_id = existing['Customer_ID']
            else:
                # AUTO_INCREMENT — DB generates Customer_ID
                ins_cur = conn.cursor()
                ins_cur.execute(
                    "INSERT INTO CUSTOMER (Name, PhnNo) VALUES (%s, %s)",
                    (customer_name, customer_phone)
                )
                cust_id = ins_cur.lastrowid
                ins_cur.close()

            # ── Step 2: Insert the bill header (Total_Amount = 0; trigger updates it) ──
            bill_cur = conn.cursor()
            bill_cur.execute(
                "INSERT INTO CUSTOMER_BILL (SaleDate, Total_Amount, Staff_ID, Customer_ID) "
                "VALUES (CURDATE(), 0.00, %s, %s)",
                (staff_id, cust_id)
            )
            new_bill_id = bill_cur.lastrowid
            bill_cur.close()

            # ── Step 3: Insert line items (trigger owns stock deduction & total update) ──
            item_cur = conn.cursor()
            for item in cart:
                item_cur.execute(
                    "INSERT INTO BILL_ITEMS (Bill_No, BatchNo, Barcode, Qty_Sold) VALUES (%s, %s, %s, %s)",
                    (new_bill_id, item['batch'], item['barcode'], item['qty'])
                )
            item_cur.close()

            conn.commit()
            return jsonify({
                'success':     True,
                'bill_no':     new_bill_id,
                'customer_id': cust_id
            })
        except Error as e:
            conn.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn.is_connected(): conn.close()
