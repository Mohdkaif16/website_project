from flask import Flask, render_template, request, redirect, session, flash, send_file
import sqlite3, os, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "kanha_secret_key"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def db():
    return sqlite3.connect('database.db')

def init_db():
    conn = db()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT, price INTEGER, stock INTEGER, image TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS cart(id INTEGER PRIMARY KEY, user_id INTEGER, product_id INTEGER, quantity INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, user_id INTEGER, total INTEGER, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER, quantity INTEGER)')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        p = generate_password_hash(request.form['password'])
        conn = db(); c = conn.cursor()
        try:
            c.execute("INSERT INTO users(username,password) VALUES (?,?)",(u,p))
            conn.commit()
            return redirect('/login')
        except:
            flash('Username exists')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        conn = db(); c = conn.cursor()
        c.execute("SELECT id,password FROM users WHERE username=?",(u,))
        data = c.fetchone()
        conn.close()
        if data and check_password_hash(data[1], p):
            session['uid'] = data[0]
            session['username'] = u
            return redirect('/products')
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/products')
def products():
    q = request.args.get('q')
    conn = db(); c = conn.cursor()
    if q:
        c.execute("SELECT * FROM products WHERE name LIKE ?",('%'+q+'%',))
    else:
        c.execute("SELECT * FROM products")
    items = c.fetchall()
    conn.close()
    return render_template('products.html', items=items)

@app.route('/add_to_cart/<int:pid>', methods=['POST'])
def add_to_cart(pid):
    qty = int(request.form['quantity'])
    conn = db(); c = conn.cursor()
    c.execute("SELECT id FROM cart WHERE user_id=? AND product_id=?", (session['uid'], pid))
    row = c.fetchone()
    if row:
        c.execute("UPDATE cart SET quantity=quantity+? WHERE id=?", (qty, row[0]))
    else:
        c.execute("INSERT INTO cart(user_id,product_id,quantity) VALUES (?,?,?)",(session['uid'],pid,qty))
    conn.commit(); conn.close()
    return redirect('/products')

@app.route('/cart')
def cart():
    conn = db(); c = conn.cursor()
    c.execute('''SELECT cart.id, products.name, products.price, cart.quantity
                 FROM cart JOIN products ON cart.product_id=products.id
                 WHERE cart.user_id=?''',(session['uid'],))
    items = c.fetchall()
    conn.close()
    return render_template('cart.html', items=items)

@app.route('/remove/<int:cid>')
def remove(cid):
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM cart WHERE id=?", (cid,))
    conn.commit(); conn.close()
    return redirect('/cart')

@app.route('/checkout')
def checkout():
    conn = db(); c = conn.cursor()
    c.execute('''SELECT products.id, products.price, cart.quantity
                 FROM cart JOIN products ON cart.product_id=products.id
                 WHERE cart.user_id=?''',(session['uid'],))
    rows = c.fetchall()
    total = sum(r[1]*r[2] for r in rows)
    c.execute("INSERT INTO orders(user_id,total,date) VALUES (?,?,?)",
              (session['uid'], total, str(datetime.datetime.now())))
    oid = c.lastrowid
    for r in rows:
        c.execute("INSERT INTO order_items(order_id,product_id,quantity) VALUES (?,?,?)",(oid,r[0],r[2]))
        c.execute("UPDATE products SET stock=stock-? WHERE id=?",(r[2],r[0]))
    c.execute("DELETE FROM cart WHERE user_id=?", (session['uid'],))
    conn.commit(); conn.close()
    return render_template('success.html', total=total, oid=oid)

@app.route('/invoice/<int:oid>')
def invoice(oid):
    doc = SimpleDocTemplate("invoice.pdf")
    styles = getSampleStyleSheet()
    elems = [Paragraph("Kanha Agro Invoice", styles['Title']),
             Paragraph(f"Order ID: {oid}", styles['Normal'])]
    doc.build(elems)
    return send_file("invoice.pdf", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
