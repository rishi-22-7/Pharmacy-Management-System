from flask import render_template, request, redirect, url_for, session, flash
from mysql.connector import Error
from db import get_db_connection, require_role, resolve_sort, resolve_order

MGR_INV_SORT = {
    'BatchNo': 'b.BatchNo', 'Name': 'd.Name',
    'ExpDate': 'b.ExpDate', 'price': 'b.Unit_Selling_Price',
    'qty':     'b.Qty_In_Stock',
}
MGR_ORD_SORT = {
    'Order_No':  'r.Order_No',
    'OrderDate': 'r.OrderDate',
    'OrderCost': 'r.OrderCost',
}

def register_manager_routes(app):
    @app.route('/manager')
    def manager():
        if not require_role('Manager'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))

        sort_inv    = request.args.get('sort_inv',        'BatchNo')
        order_inv   = resolve_order(request.args.get('order_inv', 'ASC'))
        
        sort_orders = request.args.get('sort_orders', 'OrderDate')
        order_orders= resolve_order(request.args.get('order_orders', 'DESC'))
        
        active_tab  = request.args.get('tab',         'dashboard')

        inv_col = resolve_sort(sort_inv,    MGR_INV_SORT, 'BatchNo')
        ord_col = resolve_sort(sort_orders, MGR_ORD_SORT, 'OrderDate')

        conn = get_db_connection()
        total_stock = 0; low_stock = []; batches = []
        pending_orders = 0; supplier_list = []
        restock_history = []; medicines_list = []

        if conn:
            try:
                cur = conn.cursor(dictionary=True)

                # Fetch all available medicines for dropdown
                cur.execute("""
                    SELECT Barcode, Name FROM DRUG ORDER BY Name ASC
                """)
                medicines_list = cur.fetchall()

                cur.execute("SELECT SUM(Qty_In_Stock) AS total FROM INVENTORY_BATCH")
                total_stock = int(cur.fetchone()['total'] or 0)

                cur.execute("""
                    SELECT b.BatchNo, d.Name, b.Qty_In_Stock
                    FROM INVENTORY_BATCH b JOIN DRUG d ON b.Barcode = d.Barcode
                    WHERE b.Qty_In_Stock < 20 ORDER BY b.Qty_In_Stock ASC
                """)
                low_stock = cur.fetchall()

                cur.execute(f"""
                    SELECT b.BatchNo, b.Barcode, d.Name, b.Mfg_Date, b.ExpDate,
                           b.Qty_In_Stock, b.Unit_Selling_Price
                    FROM INVENTORY_BATCH b JOIN DRUG d ON b.Barcode = d.Barcode
                    ORDER BY {inv_col} {order_inv}
                """)
                batches = cur.fetchall()

                cur.execute("SELECT COUNT(*) AS cnt FROM RESTOCK_ORDER")
                pending_orders = cur.fetchone()['cnt']

                cur.execute("SELECT * FROM SUPPLIER ORDER BY Name")
                supplier_list = cur.fetchall()

                cur.execute(f"""
                    SELECT r.Order_No, r.OrderDate, r.OrderCost, r.Company_ID,
                           COALESCE(s.Name, r.Company_ID) AS SupplierName,
                           COUNT(ri.Barcode) AS item_count,
                           SUM(ri.Qty_Ordered) AS total_qty
                    FROM RESTOCK_ORDER r
                    LEFT JOIN SUPPLIER s ON r.Company_ID = s.Company_ID
                    LEFT JOIN RESTOCK_ITEMS ri ON r.Order_No = ri.Order_No
                    GROUP BY r.Order_No, r.OrderDate, r.OrderCost,
                             r.Company_ID, SupplierName
                    ORDER BY {ord_col} {order_orders}
                """)
                restock_history = cur.fetchall()

            except Error as e:
                print(f"[MANAGER FETCH ERROR] {e}")
                flash('Could not load data.', 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()

        return render_template('manager.html',
            name=session.get('name'),
            total_stock=total_stock, low_stock=low_stock,
            pending_orders=pending_orders, batches=batches,
            supplier_list=supplier_list, restock_history=restock_history,
            medicines_list=medicines_list,
            sort_inv=sort_inv, order_inv=order_inv,
            sort_orders=sort_orders, order_orders=order_orders,
            active_tab=active_tab
        )

    @app.route('/manager/place_order', methods=['POST'])
    def manager_place_order():
        if not require_role('Manager'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))
        company_id  = request.form.get('company_id', '').strip()
        barcodes    = request.form.getlist('barcode')
        qtys        = request.form.getlist('qty_ordered')
        unit_costs  = request.form.getlist('unit_cost')
        staff_id    = session.get('staff_id')

        if not company_id:
            flash('Supplier is required.', 'error')
            return redirect(url_for('manager', tab='procurement'))
        if not barcodes:
            flash('At least one drug item is required.', 'error')
            return redirect(url_for('manager', tab='procurement'))

        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                # Insert the order header — DB generates Order_No via AUTO_INCREMENT
                # OrderCost is set to 0.00; MySQL trigger will update it after items are inserted
                cur.execute(
                    "INSERT INTO RESTOCK_ORDER (OrderDate, OrderCost, Staff_ID, Company_ID) "
                    "VALUES (CURDATE(), 0.00, %s, %s)",
                    (staff_id, company_id)
                )
                new_order_id = cur.lastrowid

                # Insert each line item
                for barcode, qty_str, cost_str in zip(barcodes, qtys, unit_costs):
                    barcode = barcode.strip()
                    if not barcode:
                        continue
                    try:
                        qty  = int(qty_str)
                        cost = float(cost_str)
                    except ValueError:
                        conn.rollback()
                        flash('Quantity and Unit Cost must be valid numbers.', 'error')
                        return redirect(url_for('manager', tab='procurement'))
                    cur.execute(
                        "INSERT INTO RESTOCK_ITEMS (Order_No, Barcode, Qty_Ordered, Unit_Cost) "
                        "VALUES (%s, %s, %s, %s)",
                        (new_order_id, barcode, qty, cost)
                    )

                conn.commit()
                flash(f"Restock Order #{new_order_id} placed successfully. Cost calculated by DB.", 'success')
            except Error as e:
                conn.rollback()
                flash(f"Error placing order: {e}", 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()
        return redirect(url_for('manager', tab='procurement'))

    @app.route('/manager/delete_bill/<int:bill_id>', methods=['POST'])
    def manager_delete_bill(bill_id):
        if not require_role('Manager'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM CUSTOMER_BILL WHERE Bill_No = %s", (bill_id,))
                conn.commit()
                flash(f'Bill #{bill_id} deleted & stock refunded.', 'success')
            except Error as e:
                flash(f'Error deleting bill: {e}', 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()
        return redirect(url_for('manager', tab='bills'))

    @app.route('/manager/intake_batch', methods=['POST'])
    def manager_intake_batch():
        if not require_role('Manager'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))
        batch_no = request.form.get('batch_no', '').strip()
        barcode  = request.form.get('barcode',  '').strip()
        mfg_date = request.form.get('mfg_date', '').strip()
        exp_date = request.form.get('exp_date', '').strip()
        qty      = request.form.get('qty',      '0').strip()
        price    = request.form.get('price',    '0').strip()
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO INVENTORY_BATCH
                      (BatchNo, Barcode, Mfg_Date, ExpDate, Qty_In_Stock, Unit_Selling_Price)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (batch_no, barcode, mfg_date, exp_date, int(qty), float(price)))
                conn.commit()
                flash('Inventory Updated Successfully.', 'success')
            except Error as e:
                flash(f"Error: {e}", 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()
        return redirect(url_for('manager', tab='procurement'))
