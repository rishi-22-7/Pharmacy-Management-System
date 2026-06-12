import os
import mysql.connector
from mysql.connector import Error
from flask import session

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', 3006)),
            database=os.environ.get('DB_NAME', 'pharmacy_db'),
            user=os.environ.get('DB_USER', 'root'),
            password=os.environ.get('DB_PASSWORD', 'Rishi_22@srm')
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"[DB ERROR] {e}")
        return None

def resolve_sort(sort_val, sort_map, default):
    return sort_map.get(sort_val, sort_map[default])

def resolve_order(order_val):
    if order_val and order_val.upper() in ['ASC', 'DESC']:
        return order_val.upper()
    return 'ASC'

def require_role(role):
    return session.get('staff_id') and session.get('role') == role
