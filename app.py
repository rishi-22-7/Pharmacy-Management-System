from flask import Flask, redirect, url_for, session, flash
from routes.auth import register_auth_routes
from routes.admin import register_admin_routes
from routes.manager import register_manager_routes
from routes.pharmacist import register_pharmacist_routes
from routes.api import register_api_routes

app = Flask(__name__)
app.secret_key = 'pharmacy_secret_key_2024'

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

# Register modular route collections
register_auth_routes(app)
register_admin_routes(app)
register_manager_routes(app)
register_pharmacist_routes(app)
register_api_routes(app)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
