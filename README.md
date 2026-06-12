<h1 align="center">🏥 Pulse Pharmacy Management System</h1>

<p align="center">
  <a href="https://pharmacy-management-system-t54e.onrender.com" target="_blank">
    <img src="https://img.shields.io/badge/Live-Demo-00C853?style=for-the-badge&logo=render&logoColor=white" alt="Live Demo" />
  </a>
  <img src="https://img.shields.io/badge/Backend-Flask-01579B?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Database-MySQL-FF8F00?style=for-the-badge&logo=mysql&logoColor=white" alt="MySQL" />
  <img src="https://img.shields.io/badge/License-MIT-ECEFF1?style=for-the-badge&logo=open-source-initiative&logoColor=black" alt="License" />
</p>

<p align="center">
  <strong>A sleek, robust, and responsive web application designed to automate pharmacy inventory, role management, transactions, and real-time shelf stock deductions.</strong>
</p>

---

## 🔑 Testing Credentials

Use the following credentials to log in and test the live demo:

<table align="center" width="100%">
  <thead>
    <tr>
      <th align="center">Role</th>
      <th align="center">Staff ID Input</th>
      <th align="center">Password</th>
      <th align="left">Access Level & Permissions</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td align="center"><strong>Admin</strong></td>
      <td align="center"><code>ADM1</code></td>
      <td align="center"><code>123456</code></td>
      <td align="left">Full system control, register/remove staff, view site metrics.</td>
    </tr>
    <tr>
      <td align="center"><strong>Manager</strong></td>
      <td align="center"><code>MGR2</code></td>
      <td align="center"><code>123456</code></td>
      <td align="left">Inventory management, vendor logs, and restock procurement.</td>
    </tr>
    <tr>
      <td align="center"><strong>Pharmacist</strong></td>
      <td align="center"><code>PHR3</code></td>
      <td align="center"><code>123456</code></td>
      <td align="left">POS billing interface, customer profiles, doctor registries.</td>
    </tr>
  </tbody>
</table>

---

## ⚡ Core Features

<details open>
  <summary>🔑 <strong>Dynamic Role-Based Access Control (RBAC)</strong></summary>
  <br>
  <ul>
    <li><strong>Admin (<code>ADM</code>)</strong>: Full system access, registering/removing staff, and financial oversight.</li>
    <li><strong>Manager (<code>MGR</code>)</strong>: Inventory management, vendor procurement, and replenishment orders.</li>
    <li><strong>Pharmacist (<code>PHR</code>)</strong>: Point-of-Sale (POS) billing, doctor referrals, and patient records.</li>
  </ul>
</details>

<details>
  <summary>📦 <strong>ACID-Compliant MySQL Database</strong></summary>
  <br>
  <ul>
    <li>Integrated with a cloud-hosted 3NF relational database.</li>
    <li>Uses transaction safety to prevent data corruption.</li>
  </ul>
</details>

<details>
  <summary>⚡ <strong>Automated SQL Triggers</strong></summary>
  <br>
  <ul>
    <li>Smart triggers automatically adjust physical batch shelf stock upon POS billing transactions to prevent stockouts and overselling.</li>
  </ul>
</details>

<details>
  <summary>🏷️ <strong>Batch & Expiry Control</strong></summary>
  <br>
  <ul>
    <li>Monitor catalog medicines at the batch level to track exact manufacturing and expiration dates.</li>
  </ul>
</details>

---

## 🛠️ Technology Stack

<table align="center" width="100%">
  <tr>
    <td align="center" width="25%">
      <strong>Frontend</strong><br>
      HTML5 / CSS3 / JS<br>
      (Responsive Sidebar, Glassmorphism)
    </td>
    <td align="center" width="25%">
      <strong>Backend</strong><br>
      Python / Flask<br>
      (Modular routes, blueprints)
    </td>
    <td align="center" width="25%">
      <strong>Database</strong><br>
      MySQL<br>
      (Hosted on Aiven Cloud)
    </td>
    <td align="center" width="25%">
      <strong>Hosting</strong><br>
      Render<br>
      (Automated Web Service)
    </td>
  </tr>
</table>

---

## 🗄️ Database Architecture

<details>
  <summary>📂 <strong>Entity Relationship Schema</strong></summary>
  <br>
  <ul>
    <li><strong>Master Records</strong>: <code>DRUG</code>, <code>DRUG_CATEGORY</code>, <code>SUPPLIER</code>, <code>STAFF</code>, <code>CUSTOMER</code>, <code>DOCTOR</code></li>
    <li><strong>Transactional & Junction Data</strong>: <code>INVENTORY_BATCH</code>, <code>CUSTOMER_BILL</code>, <code>BILL_ITEMS</code>, <code>RESTOCK_ORDER</code>, <code>RESTOCK_ITEMS</code></li>
  </ul>
</details>

---

## 🚀 Local Setup & Installation

### Prerequisites
- Python 3.8+
- MySQL Server 8.0+

### Step-by-Step Guide

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/rishi-22-7/Pharmacy-Management-System.git
   cd Pharmacy-Management-System
   ```

2. **Set Up a Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Database Configuration:**
   Configure your database environment variables or edit the default fallback values in `db.py`:
   - `DB_HOST`: Host address of your MySQL database
   - `DB_PORT`: Database port (default: `3306`)
   - `DB_NAME`: Schema name (e.g., `defaultdb` or `pharmacy_db`)
   - `DB_USER`: Database username
   - `DB_PASSWORD`: Database password

5. **Run the Application:**
   ```bash
   python app.py
   ```
   Open your browser and navigate to `http://127.0.0.1:5000/`.

---

## 👥 Authors

* **Majeti Naga Sai Rishi**

---

## 📝 License

This project is licensed under the MIT License.
