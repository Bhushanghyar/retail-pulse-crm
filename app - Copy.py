import sqlite3
import pandas as pd
import json
import plotly
import plotly.express as px
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = 'bhushan_enterprise_key'

# --- DATABASE CONNECTION ---
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- SECURITY ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: 
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- HOME ROUTE ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# --- AUTHENTICATION ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (request.form['username'],)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        flash("Invalid Credentials")
    return render_template('login.html', shop_name="Bhushan Enterprises")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD & PRICE ALERTS ---
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    revenue = conn.execute("SELECT SUM(total_price) FROM orders").fetchone()[0] or 0
    profit = conn.execute('''
        SELECT SUM(orders.total_price - (orders.quantity * products.cost_price)) 
        FROM orders JOIN products ON orders.product_id = products.id
    ''').fetchone()[0] or 0
    
    price_alerts = conn.execute('''
        SELECT name, price, market_price,
        CASE 
            WHEN price > (market_price * 1.15) THEN 'Overpriced'
            WHEN price < (market_price * 0.85) THEN 'Underpriced'
            ELSE 'Healthy'
        END as alert_status
        FROM products WHERE market_price > 0 AND alert_status != 'Healthy'
    ''').fetchall()

    stats = {
        'customers': conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        'products': conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        'orders': conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        'revenue': revenue,
        'profit': profit,
        'staff_stats': conn.execute("SELECT assigned_to, COUNT(*) as lead_count FROM leads GROUP BY assigned_to ORDER BY lead_count DESC LIMIT 5").fetchall()
    }
    low_stock = conn.execute("SELECT name, stock FROM products WHERE stock < 5").fetchall()
    conn.close()
    return render_template('dashboard.html', **stats, low_stock=low_stock, price_alerts=price_alerts)

# --- CUSTOMER MANAGEMENT ---
@app.route('/customers', methods=['GET', 'POST'])
@login_required
def customers():
    conn = get_db()
    if request.method == 'POST':
        conn.execute("INSERT INTO customers (name, phone, email, address) VALUES (?,?,?,?)",
                     (request.form['name'], request.form['phone'], request.form['email'], request.form['address']))
        conn.commit()
        return redirect(url_for('customers'))
    search = request.args.get('search', '')
    data = conn.execute("SELECT * FROM customers WHERE name LIKE ?", ('%' + search + '%',)).fetchall()
    conn.close()
    return render_template('customers.html', customers=data)

# --- CUSTOMER PROFILE ---
@app.route('/customer/<int:id>')
@login_required
def customer_profile(id):
    conn = get_db()
    customer = conn.execute("SELECT * FROM customers WHERE id=?", (id,)).fetchone()
    if not customer:
        conn.close()
        return "Customer not found", 404
    
    history = conn.execute('''
        SELECT orders.*, products.name as p_name 
        FROM orders 
        JOIN products ON orders.product_id = products.id 
        WHERE orders.customer_id=? 
        ORDER BY orders.date DESC
    ''', (id,)).fetchall()

    # ADDED: This line fetches the history for the Interaction Timeline
    interactions = conn.execute("SELECT * FROM interactions WHERE customer_id=? ORDER BY date DESC", (id,)).fetchall()
    
    conn.close()
    return render_template('customer_profile.html', customer=customer, history=history, interactions=interactions)

# --- ADDED: NEW ROUTE TO FIX LOG EVENT ERROR ---
@app.route('/add_interaction/<int:id>', methods=['POST'])
@login_required
def add_interaction(id):
    conn = get_db()
    # Records the interaction type (Call, Email, etc.) and notes to the database
    conn.execute("INSERT INTO interactions (customer_id, type, notes, date) VALUES (?, ?, ?, ?)",
                 (id, request.form['type'], request.form['notes'], datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()
    # Redirects back to the profile page so you see the updated timeline
    return redirect(url_for('customer_profile', id=id))

# --- LEADS ---
@app.route('/leads', methods=['GET', 'POST'])
@login_required
def leads():
    conn = get_db()
    if request.method == 'POST':
        conn.execute("INSERT INTO leads (name, contact, notes, assigned_to) VALUES (?,?,?,?)",
                     (request.form['name'], request.form['contact'], request.form['notes'], session.get('username')))
        conn.commit()
        return redirect(url_for('leads'))
    data = conn.execute("SELECT * FROM leads").fetchall()
    conn.close()
    return render_template('leads.html', leads=data)

# --- INVENTORY ---
@app.route('/products', methods=['GET', 'POST'])
@login_required
def products():
    conn = get_db()
    if request.method == 'POST':
        conn.execute("INSERT INTO products (name, price, cost_price, stock) VALUES (?,?,?,?)", 
                     (request.form['name'], request.form['price'], request.form['cost_price'], request.form['stock']))
        conn.commit()
        return redirect(url_for('products'))
    data = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template('products.html', products=data)

# --- SALES ---
@app.route('/orders', methods=['GET', 'POST'])
@login_required
def orders():
    conn = get_db()
    if request.method == 'POST':
        p = conn.execute("SELECT price, stock FROM products WHERE id=?", (request.form['product_id'],)).fetchone()
        qty = int(request.form['quantity'])
        if p and p['stock'] >= qty:
            total = p['price'] * qty
            conn.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, request.form['product_id']))
            conn.execute("INSERT INTO orders (customer_id, product_id, quantity, total_price, date) VALUES (?,?,?,?,?)",
                         (request.form['customer_id'], request.form['product_id'], qty, total, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
        else:
            flash("Insufficient stock!")
        return redirect(url_for('orders'))

    orders_data = conn.execute('''SELECT orders.*, customers.name, products.name as p_name 
                                  FROM orders 
                                  JOIN customers ON orders.customer_id = customers.id 
                                  JOIN products ON orders.product_id = products.id''').fetchall()
    customers_list = conn.execute("SELECT id, name FROM customers").fetchall()
    products_list = conn.execute("SELECT id, name, price FROM products").fetchall()
    conn.close()
    return render_template('orders.html', orders=orders_data, customers=customers_list, products=products_list)

# --- BILL DOWNLOAD ---
@app.route('/download_invoice/<int:id>')
@login_required
def download_invoice(id):
    conn = get_db()
    query = '''
        SELECT orders.*, customers.name as c_name, customers.phone, products.name as p_name, products.price as unit_price
        FROM orders 
        JOIN customers ON orders.customer_id = customers.id 
        JOIN products ON orders.product_id = products.id 
        WHERE orders.id=?
    '''
    order = conn.execute(query, (id,)).fetchone()
    conn.close()

    if not order:
        return "Invoice Not Found", 404

    invoice_text = f"""
    ========================================
    BHUSHAN ENTERPRISES - OFFICIAL BILL
    ========================================
    Invoice ID: #INV-{order['id']}
    Date: {order['date']}
    
    CUSTOMER: {order['c_name']}
    PHONE: {order['phone']}
    
    ITEM: {order['p_name']}
    QTY: {order['quantity']}
    PRICE: ₹{order['unit_price']}
    ----------------------------------------
    TOTAL PAID: ₹{order['total_price']}
    ========================================
    Thank you for your business!
    """
    return send_file(io.BytesIO(invoice_text.encode()), mimetype='text/plain', as_attachment=True, download_name=f"Bhushan_Bill_{id}.txt")

# --- REPORTS ---
@app.route('/reports')
@login_required
def reports():
    conn = get_db()
    query = 'SELECT orders.date, orders.total_price, products.cost_price, orders.quantity FROM orders JOIN products ON orders.product_id = products.id'
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return render_template('reports.html', graphJSON=None)
    
    df['total_price'] = pd.to_numeric(df['total_price'], errors='coerce').fillna(0)
    df['cost_price'] = pd.to_numeric(df['cost_price'], errors='coerce').fillna(0)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['Month'] = df['date'].dt.strftime('%b %Y')
    df['Profit'] = df['total_price'] - (df['quantity'] * df['cost_price'])
    
    m_df = df.groupby('Month').agg({'total_price': 'sum', 'Profit': 'sum'}).reset_index()
    m_df.columns = ['Month', 'Revenue', 'Profit']

    fig = px.bar(m_df, x='Month', y=['Revenue', 'Profit'], barmode='group', title='Monthly Growth',
                 color_discrete_map={'Revenue': '#2563EB', 'Profit': '#10B981'})
    
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return render_template('reports.html', graphJSON=graphJSON)

# --- ADMIN FEATURES ---
@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if session.get('role') != 'Admin':
        return redirect(url_for('dashboard'))
    conn = get_db()
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'])
        try:
            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                         (request.form['username'], hashed_pw, request.form['role']))
            conn.commit()
        except:
            flash("User already exists!")
    users = conn.execute("SELECT id, username, role FROM users").fetchall()
    conn.close()
    return render_template('manage_users.html', users=users)

@app.route('/delete/<string:table_type>/<int:item_id>')
@login_required
def delete_item(table_type, item_id):
    if session.get('role') != 'Admin': 
        return redirect(url_for('dashboard'))
    conn = get_db()
    valid_tables = ['customers', 'products', 'leads', 'orders', 'users']
    if table_type in valid_tables:
        conn.execute(f"DELETE FROM {table_type} WHERE id=?", (item_id,))
        conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)