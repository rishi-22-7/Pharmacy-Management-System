from flask import render_template, request, redirect, url_for, session, flash
from mysql.connector import Error
from db import get_db_connection

def register_auth_routes(app):
    @app.route('/', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            staff_id_input = request.form.get('staff_id', '').strip()
            login_role    = request.form.get('login_role',    '').strip()
            password_input = request.form.get('password',     '').strip()
            
            # Parse the prefix (e.g., ADM1, MGR2, PHR3)
            import re
            match = re.match(r'^([a-zA-Z]+)?(\d+)$', staff_id_input)
            if not match:
                flash('Invalid Staff ID format. Use prefixes like ADM1, MGR2, or PHR3.', 'error')
                return redirect(url_for('login'))
            
            prefix, numeric_id = match.group(1), match.group(2)
            expected_prefix = {'Admin': 'ADM', 'Manager': 'MGR', 'Pharmacist': 'PHR'}.get(login_role, '')
            
            if not prefix:
                flash(f'Prefix is required. Please use {expected_prefix}{numeric_id} for your ID.', 'error')
                return redirect(url_for('login'))
                
            if prefix.upper() != expected_prefix:
                flash(f'ID prefix "{prefix.upper()}" does not match selected role. Expected "{expected_prefix}".', 'error')
                return redirect(url_for('login'))
                
            staff_id = int(numeric_id)

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
