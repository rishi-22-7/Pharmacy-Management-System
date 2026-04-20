from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import date

app = Flask(__name__)
app.secret_key = 'pharmacy_secret_key_2024'


# ──────────────────────────────────────────────
#  Database Connection
# ──────────────────────────────────────────────
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost', port=3006,
            database='pharmacy_db', user='root',
            password='Rishi_22@srm'
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"[DB ERROR] {e}")
        return None


# ──────────────────────────────────────────────
#  Safe Sort Helper (prevents SQL injection)
# ──────────────────────────────────────────────
def resolve_sort(sort_val, sort_map, default):
    return sort_map.get(sort_val, sort_map[default])

def resolve_order(order_val):
    if order_val and order_val.upper() in ['ASC', 'DESC']:
        return order_val.upper()
    return 'ASC'

def require_role(role):
    return session.get('staff_id') and session.get('role') == role


# ──────────────────────────────────────────────
#  Login / Logout
# ──────────────────────────────────────────────
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        staff_id      = request.form.get('staff_id',      '').strip()
        login_role    = request.form.get('login_role',    '').strip()
        password_input = request.form.get('password',     '').strip()
        conn = get_db_connection()
        if conn is None:
            flash('Database connection failed.', 'error')
            return redirect(url_for('login'))
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT Name, Role, Password FROM STAFF WHERE Staff_ID = %s AND Role = %s",
                (staff_id, login_role)
            )
            member = cur.fetchone()
            if member:
                stored_hash = member.get('Password') or ''
                # If no password set yet, block login
                if not stored_hash:
                    flash('No password set for this account. Contact your administrator.', 'error')
                else:
                    if stored_hash == password_input:
                        session['staff_id'] = staff_id
                        session['name']     = member['Name']
                        session['role']     = member['Role']
                        return redirect(url_for('dashboard'))
                    else:
                        flash('Incorrect password. Please try again.', 'error')
            else:
                flash('Invalid Staff ID or Role. Please try again.', 'error')
        except Error as e:
            print(f"[LOGIN ERROR] {e}")
            flash('An error occurred. Please try again.', 'error')
        finally:
            if conn.is_connected(): cur.close(); conn.close()
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


# ──────────────────────────────────────────────
#  Dashboard Traffic Cop
# ──────────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'staff_id' not in session:
        flash('Please log in to access the dashboard.', 'error')
        return redirect(url_for('login'))
    role = session.get('role', '')
    if   role == 'Pharmacist': return redirect(url_for('pharmacist'))
    elif role == 'Manager':    return redirect(url_for('manager'))
    elif role == 'Admin':      return redirect(url_for('admin'))
    flash('Unknown role.', 'error')
    return redirect(url_for('login'))


# ══════════════════════════════════════════════
#  ADMIN — GOD MODE
# ══════════════════════════════════════════════

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


# ══════════════════════════════════════════════
#  MANAGER PORTAL
# ══════════════════════════════════════════════

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


# ══════════════════════════════════════════════
#  PHARMACIST PORTAL
# ══════════════════════════════════════════════

PHARM_SORT = {
    'Name':    'd.Name',
    'price':   'b.Unit_Selling_Price',
    'qty':     'b.Qty_In_Stock',
    'BatchNo': 'b.BatchNo',
}


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


# ──────────────────────────────────────────────
#  Profile & Change Password
# ──────────────────────────────────────────────
@app.route('/profile')
def profile():
    if 'staff_id' not in session:
        flash('Please log in to access your profile.', 'error')
        return redirect(url_for('login'))
    staff_id = session.get('staff_id')
    conn = get_db_connection()
    user = None
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT Staff_ID, Name, Role, Phone FROM STAFF WHERE Staff_ID = %s",
                        (staff_id,))
            user = cur.fetchone()
        except Error as e:
            print(f"[PROFILE ERROR] {e}")
            flash('Could not load profile data.', 'error')
        finally:
            if conn.is_connected(): cur.close(); conn.close()
    return render_template('profile.html', user=user)


@app.route('/change_password', methods=['POST'])
def change_password():
    if 'staff_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login'))
    staff_id        = session.get('staff_id')
    current_password = request.form.get('current_password', '')
    new_password    = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed.', 'error')
        return redirect(url_for('profile'))
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT Password FROM STAFF WHERE Staff_ID = %s", (staff_id,))
        row = cur.fetchone()
        
        stored_hash = row['Password'] if row and row['Password'] else ''
        
        if stored_hash != current_password:
            flash('Incorrect current password.', 'error')
            return redirect(url_for('profile'))
            
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('profile'))

        cur2 = conn.cursor()
        cur2.execute("UPDATE STAFF SET Password = %s WHERE Staff_ID = %s",
                     (new_password, staff_id))
        conn.commit()
        flash('Password updated successfully!', 'success')
    except Error as e:
        flash(f'Error updating password: {e}', 'error')
    finally:
        if conn.is_connected(): conn.close()
    return redirect(url_for('profile'))


# ──────────────────────────────────────────────
#  Entry Point
# ──────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, port=5000)
