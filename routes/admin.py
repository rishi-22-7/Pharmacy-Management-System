from flask import render_template, request, redirect, url_for, session, flash
from mysql.connector import Error
from db import get_db_connection, require_role, resolve_sort, resolve_order

ADMIN_INV_SORT = {
    'BatchNo':  'b.BatchNo',
    'Name':     'd.Name',
    'ExpDate':  'b.ExpDate',
    'price':    'b.Unit_Selling_Price',
    'qty':      'b.Qty_In_Stock',
}
ADMIN_STAFF_SORT = {
    'Staff_ID': 'Staff_ID',
    'Name':     'Name',
    'Role':     'Role',
}
ADMIN_SUP_SORT = {
    'Company_ID': 'Company_ID',
    'Name':       'Name',
    'City':       'City',
}
ADMIN_DRUG_SORT = {
    'Barcode': 'd.Barcode',
    'Name':    'd.Name',
    'Dose':    'd.Dose',
    'Category': 'dc.CategoryName',
    'Supplier': 's.Name',
}

def register_admin_routes(app):
    @app.route('/admin')
    def admin():
        if not require_role('Admin'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))

        sort_inv   = request.args.get('sort_inv',   'BatchNo')
        order_inv  = resolve_order(request.args.get('order_inv', 'ASC'))
        
        sort_staff = request.args.get('sort_staff', 'Staff_ID')
        order_staff= resolve_order(request.args.get('order_staff', 'ASC'))
        
        sort_sup   = request.args.get('sort_sup',   'Company_ID')
        order_sup  = resolve_order(request.args.get('order_sup', 'ASC'))
        
        sort_drug  = request.args.get('sort_drug',  'Name')
        order_drug = resolve_order(request.args.get('order_drug', 'ASC'))
        
        active_tab = request.args.get('tab',        'staff')

        inv_col   = resolve_sort(sort_inv,   ADMIN_INV_SORT,   'BatchNo')
        staff_col = resolve_sort(sort_staff, ADMIN_STAFF_SORT, 'Staff_ID')
        sup_col   = resolve_sort(sort_sup,   ADMIN_SUP_SORT,   'Company_ID')
        drug_col  = resolve_sort(sort_drug,  ADMIN_DRUG_SORT,  'Name')

        conn = get_db_connection()
        staff_list = []; inventory_list = []; supplier_list = []
        bills_list = []; total_revenue = 0; total_items = 0
        top_medicine = None; suppliers = []; drugs_list = []

        if conn:
            try:
                cur = conn.cursor(dictionary=True)

                # Fetch suppliers for Master Catalog
                cur.execute("SELECT Company_ID, Name FROM SUPPLIER ORDER BY Name ASC")
                suppliers = cur.fetchall()

                # Fetch all drugs with category and supplier info
                cur.execute(f"""
                    SELECT d.Barcode, d.Name, d.Dose, dc.CategoryName, s.Name AS SupplierName
                    FROM DRUG d
                    LEFT JOIN DRUG_CATEGORY dc ON d.Category_ID = dc.Category_ID
                    LEFT JOIN SUPPLIER s ON d.Company_ID = s.Company_ID
                    ORDER BY {drug_col} {order_drug}
                """)
                drugs_list = cur.fetchall()

                cur.execute(f"SELECT * FROM STAFF ORDER BY {staff_col} {order_staff}")
                staff_list = cur.fetchall()

                cur.execute(f"""
                    SELECT b.BatchNo, b.Barcode, d.Name, b.Mfg_Date,
                           b.ExpDate, b.Qty_In_Stock, b.Unit_Selling_Price
                    FROM INVENTORY_BATCH b
                    JOIN DRUG d ON b.Barcode = d.Barcode
                    ORDER BY {inv_col} {order_inv}
                """)
                inventory_list = cur.fetchall()

                cur.execute(f"SELECT * FROM SUPPLIER ORDER BY {sup_col} {order_sup}")
                supplier_list = cur.fetchall()

                # ── Billing Analytics (Live All-Time Data) ──
                cur.execute("""
                    SELECT cb.Bill_No, cb.SaleDate, cb.Total_Amount,
                           s.Name  AS StaffName,
                           c.Name  AS CustomerName,
                           c.PhnNo AS CustomerPhone
                    FROM CUSTOMER_BILL cb
                    LEFT JOIN STAFF    s ON cb.Staff_ID    = s.Staff_ID
                    LEFT JOIN CUSTOMER c ON cb.Customer_ID = c.Customer_ID
                    ORDER BY cb.SaleDate DESC, cb.Bill_No DESC
                """)
                bills_list = cur.fetchall()

                cur.execute("SELECT SUM(Total_Amount) as rev FROM CUSTOMER_BILL")
                row_rev = cur.fetchone()
                total_revenue = float(row_rev['rev'] or 0)

                cur.execute("SELECT SUM(Qty_Sold) as items FROM BILL_ITEMS")
                row_items = cur.fetchone()
                total_items = int(row_items['items'] or 0)

                cur.execute("""
                    SELECT d.Name, SUM(bi.Qty_Sold) as total_sold 
                    FROM BILL_ITEMS bi 
                    JOIN INVENTORY_BATCH b ON bi.BatchNo = b.BatchNo AND bi.Barcode = b.Barcode 
                    JOIN DRUG d ON b.Barcode = d.Barcode 
                    GROUP BY d.Name 
                    ORDER BY total_sold DESC 
                    LIMIT 1
                """)
                top_medicine = cur.fetchone()

            except Error as e:
                print(f"[ADMIN FETCH ERROR] {e}")
                flash('Could not load some dashboard data.', 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()

        return render_template('admin.html',
            name=session.get('name'),
            staff_list=staff_list, inventory_list=inventory_list,
            supplier_list=supplier_list, billing_records=bills_list,
            total_revenue=total_revenue, total_items=total_items,
            top_medicine=top_medicine,
            suppliers=suppliers, drugs_list=drugs_list,
            sort_inv=sort_inv, order_inv=order_inv,
            sort_staff=sort_staff, order_staff=order_staff,
            sort_sup=sort_sup, order_sup=order_sup,
            sort_drug=sort_drug, order_drug=order_drug,
            active_tab=active_tab
        )

    @app.route('/admin/add_staff', methods=['POST'])
    def admin_add_staff():
        if not require_role('Admin'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))
        name  = request.form.get('name',  '').strip()
        role  = request.form.get('role',  '').strip()
        phone = request.form.get('phone', '').strip()
        default_hash = '123456'
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO STAFF (Name, Role, Phone, Password) VALUES (%s, %s, %s, %s)",
                            (name, role, phone, default_hash))
                conn.commit()
                new_id = cur.lastrowid
                flash(f"Staff '{name}' (ID: {new_id}) added. Default password: 123456", 'success')
            except Error as e:
                flash(f"Error adding staff: {e}", 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()
        return redirect(url_for('admin', tab='staff'))

    @app.route('/admin/add_drug', methods=['POST'])
    def admin_add_drug():
        if not require_role('Admin'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))
        
        barcode = request.form.get('barcode', '').strip()
        name = request.form.get('name', '').strip()
        dose = request.form.get('dose', '').strip()
        category_name = request.form.get('category_name', '').strip()
        company_id = request.form.get('company_id', '').strip()
        
        if not barcode or not name:
            flash('Barcode and Medicine Name are required.', 'error')
            return redirect(url_for('admin', tab='catalog'))
        
        if not category_name or not company_id:
            flash('Category and Supplier are required.', 'error')
            return redirect(url_for('admin', tab='catalog'))
        
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                
                # First, check if category exists; if not, create it
                cur.execute("SELECT Category_ID FROM DRUG_CATEGORY WHERE CategoryName = %s", (category_name,))
                cat_result = cur.fetchone()
                
                if not cat_result:
                    # Category doesn't exist, create it
                    cur.execute("INSERT INTO DRUG_CATEGORY (CategoryName) VALUES (%s)", (category_name,))
                    conn.commit()
                    category_id = cur.lastrowid
                else:
                    category_id = cat_result[0]
                
                # Now insert the drug
                cur.execute(
                    "INSERT INTO DRUG (Barcode, Name, Dose, Category_ID, Company_ID) VALUES (%s, %s, %s, %s, %s)",
                    (barcode, name, dose or None, category_id, company_id)
                )
                conn.commit()
                flash(f"Medicine '{name}' registered successfully in category '{category_name}'.", 'success')
            except Error as e:
                conn.rollback()
                flash(f"Error adding medicine: {e}", 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()
        return redirect(url_for('admin', tab='catalog'))

    @app.route('/admin/delete_staff/<staff_id>', methods=['POST'])
    def admin_delete_staff(staff_id):
        if not require_role('Admin'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT Role FROM STAFF WHERE Staff_ID = %s", (staff_id,))
                target = cur.fetchone()
                if target and target['Role'] == 'Admin':
                    cur.execute("SELECT COUNT(*) AS cnt FROM STAFF WHERE Role = 'Admin'")
                    if cur.fetchone()['cnt'] <= 1:
                        flash('Action Denied: You cannot delete the last System Admin.', 'error')
                        return redirect(url_for('admin', tab='staff'))
                cur2 = conn.cursor()
                cur2.execute("DELETE FROM STAFF WHERE Staff_ID = %s", (staff_id,))
                conn.commit()
                flash(f"Staff member '{staff_id}' removed successfully.", 'success')
            except Error as e:
                flash(f"Error: {e}", 'error')
            finally:
                if conn.is_connected(): conn.close()
        return redirect(url_for('admin', tab='staff'))

    @app.route('/admin/add_supplier', methods=['POST'])
    def admin_add_supplier():
        if not require_role('Admin'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))
        name  = request.form.get('name',  '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        city  = request.form.get('city',  '').strip()
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO SUPPLIER (Name, Email, Phone, City) VALUES (%s,%s,%s,%s)",
                            (name, email or None, phone or None, city or None))
                conn.commit()
                new_id = cur.lastrowid
                flash(f"Supplier '{name}' (ID: {new_id}) added successfully.", 'success')
            except Error as e:
                flash(f"Error adding supplier: {e}", 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()
        return redirect(url_for('admin', tab='suppliers'))

    @app.route('/admin/delete_supplier/<company_id>', methods=['POST'])
    def admin_delete_supplier(company_id):
        if not require_role('Admin'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM SUPPLIER WHERE Company_ID = %s", (company_id,))
                conn.commit()
                flash(f"Supplier '{company_id}' removed successfully.", 'success')
            except Error as e:
                flash(f"Error: {e}", 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()
        return redirect(url_for('admin', tab='suppliers'))

    @app.route('/admin/update_price', methods=['POST'])
    def admin_update_price():
        if not require_role('Admin'):
            flash('Unauthorized Access.', 'error')
            return redirect(url_for('login'))
        batch_no  = request.form.get('batch_no',  '').strip()
        barcode   = request.form.get('barcode',   '').strip()
        new_price = request.form.get('new_price', '0').strip()
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE INVENTORY_BATCH SET Unit_Selling_Price = %s WHERE BatchNo = %s AND Barcode = %s",
                    (float(new_price), batch_no, barcode)
                )
                conn.commit()
                flash(f"Price Updated Successfully for batch {batch_no}.", 'success')
            except Error as e:
                flash(f"Error updating price: {e}", 'error')
            finally:
                if conn.is_connected(): cur.close(); conn.close()
        return redirect(url_for('admin', tab='inventory'))
