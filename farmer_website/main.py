from flask import Flask, render_template, redirect, url_for, request, flash, session, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from models import db, Farmer, Product, Order, Customer  # Import Customer model
from config import Config
from flask_migrate import Migrate 
import os

app = Flask(__name__)
app.config.from_object(Config)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to store uploaded images
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize the database
db.init_app(app)
migrate = Migrate(app, db)

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def password_matches(stored_password, provided_password):
    if not stored_password:
        return False
    if stored_password.startswith(('pbkdf2:', 'scrypt:', 'sha1:', 'bcrypt:', 'argon2:')):
        return check_password_hash(stored_password, provided_password)
    return stored_password == provided_password

# Home Page
@app.route('/')
def home():
    return render_template('base.html')

# Farmer Signup Page
@app.route('/farmer_signup', methods=['GET', 'POST'])
def farmer_signup():
    if request.method == 'POST':
        farmer_name = request.form['farmer_name']
        mobile_no = request.form['mobile_no']
        district = request.form['district']
        village = request.form['village']
        city = request.form['city']
        state = request.form['state']
        acres_owned = request.form['acres_owned']
        annual_income = request.form['annual_income']
        email = (request.form['email'] or '').strip().lower()
        password = request.form['password']

        # Check if the email already exists
        existing_farmer = Farmer.query.filter_by(email=email).first()
        if existing_farmer:
            flash('Email already exists. Please log in.')
            return redirect(url_for('farmer_login'))

        # Create a new farmer and save to the database
        new_farmer = Farmer(
            name=farmer_name, mobile_no=mobile_no, district=district,
            village=village, city=city, state=state,
            acres_owned=acres_owned, annual_income=annual_income,
            email=email, password=generate_password_hash(password)
        )
        db.session.add(new_farmer)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Email already exists. Please log in.')
            return redirect(url_for('farmer_login'))

        flash('Signup Successful! Please log in.')
        return redirect(url_for('farmer_login'))

    return render_template('signup.html')

# Farmer Login Page
@app.route('/farmer_login', methods=['GET', 'POST'])
def farmer_login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html')

        # Check if the farmer exists in the database
        farmer = Farmer.query.filter_by(email=email).first()
        if farmer and password_matches(farmer.password, password):
            session.clear()
            session['farmer_id'] = farmer.farmer_id
            flash('Login Successful!', 'success')
            return redirect(url_for('farmer_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
            return render_template('login.html')

    return render_template('login.html')

# Farmer Dashboard
@app.route('/farmer_dashboard', methods=['GET'])
def farmer_dashboard():
    farmer_id = session.get('farmer_id')  # Get the logged-in farmer's ID
    if farmer_id is None:
        flash('Please log in to access your dashboard.')
        return redirect(url_for('farmer_login'))
    
    products = Product.query.filter_by(farmer_id=farmer_id).all()  # Fetch products for the logged-in farmer
    orders = Order.query.join(Product).filter(Product.farmer_id == farmer_id).all()
    pending_count = sum(1 for order in orders if order.transport_status != 'Delivered')
    return render_template('farmer_dashboard.html', products=products, pending_count=pending_count)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    farmer_id = session.get('farmer_id')
    if farmer_id is None:
        flash('Please log in to add products.')
        return redirect(url_for('farmer_login'))

    if request.method == 'POST':
        name = request.form['name']
        image_file = request.files.get('image')  # Safely get the image file
        cost = request.form['cost']
        quantity = request.form['quantity']

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Ensure the upload folder exists
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            image_file.save(image_path)

            # Store image path relative to the static folder
            relative_image_path = os.path.join('static/images', filename)

            new_product = Product(
                farmer_id=farmer_id,
                name=name,
                image=relative_image_path,  # Save the relative path to the database
                cost=cost,
                quantity=quantity
            )
            db.session.add(new_product)
            db.session.commit()

            flash('Product added successfully!')
            return redirect(url_for('farmer_dashboard'))
        else:
            flash('Invalid image file or no image uploaded.')

    return render_template('add_product.html')


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    farmer_id = session.get('farmer_id')
    if farmer_id is None:
        flash('Please log in to edit products.')
        return redirect(url_for('farmer_login'))

    product = Product.query.get(product_id)
    if product is None or product.farmer_id != farmer_id:
        flash('Product not found or you do not have permission to edit it.')
        return redirect(url_for('farmer_dashboard'))

    if request.method == 'POST':
        product.name = request.form['name']
        image_file = request.files.get('image')  # Safely get the image file
        product.cost = request.form['cost']
        product.quantity = request.form['quantity']

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Ensure the upload folder exists
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            image_file.save(image_path)
            product.image = os.path.join('static/images', filename)  # Update with relative path

        db.session.commit()

        flash('Product updated successfully!')
        return redirect(url_for('farmer_dashboard'))

    return render_template('edit_product.html', product=product)

# Delete Product
@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    farmer_id = session.get('farmer_id')
    if farmer_id is None:
        flash('Please log in to delete products.')
        return redirect(url_for('farmer_login'))

    product = Product.query.get(product_id)
    if product and product.farmer_id == farmer_id:
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!')
    else:
        flash('Product not found or you do not have permission to delete it.')

    return redirect(url_for('farmer_dashboard'))

# View Farmer Orders and Transport Coordination
@app.route('/farmer_orders', methods=['GET'])
def farmer_orders():
    farmer_id = session.get('farmer_id')
    if farmer_id is None:
        flash('Please log in to view your orders.')
        return redirect(url_for('farmer_login'))

    orders = Order.query.join(Product).filter(Product.farmer_id == farmer_id).all()
    return render_template('ordered_customer.html', orders=orders)

# View Customer Order History
@app.route('/customer_orders', methods=['GET'])
def customer_orders():
    customer_id = session.get('customer_id')
    if customer_id is None:
        flash('Please log in to view your orders.')
        return redirect(url_for('customer_login'))

    orders = Order.query.filter_by(customer_id=customer_id).all()
    return render_template('customer_orders.html', orders=orders)

# Customer Signup Page
@app.route('/customer_signup', methods=['GET', 'POST'])
def customer_signup():
    if request.method == 'POST':
        # Get customer details from form
        name = request.form.get('name')
        email = (request.form.get('email') or '').strip().lower()
        phone_no = request.form.get('phone_no')
        address = request.form.get('address')
        password = request.form.get('password')

        # Validate form inputs
        if not all([name, email, phone_no, address, password]):
            flash('Please fill in all fields.')
            return redirect(url_for('customer_signup'))

        # Check if the email already exists
        existing_customer = Customer.query.filter_by(email=email).first()
        if existing_customer:
            flash('Email already exists. Please log in.')
            return redirect(url_for('customer_login'))

        # Create a new customer and save to the database
        new_customer = Customer(
            name=name, 
            email=email, 
            phone_no=phone_no, 
            address=address, 
            password=generate_password_hash(password)  # Hash the password
        )
        db.session.add(new_customer)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Email already exists. Please log in.')
            return redirect(url_for('customer_login'))

        flash('Signup successful! Please log in.')
        return redirect(url_for('customer_login'))

    return render_template('customer_signup.html')

# Customer Login Page
@app.route('/customer_login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password')

        # Validate form inputs
        if not email or not password:
            flash('Please fill in all fields.')
            return redirect(url_for('customer_login'))

        # Check if the customer exists in the database
        customer = Customer.query.filter_by(email=email).first()
        if customer and password_matches(customer.password, password):
            session['customer_id'] = customer.customer_id  # Store customer_id in session
            flash('Login successful!')
            return redirect(url_for('customer_dashboard'))  # Redirect to customer dashboard after login
        else:
            flash('Invalid credentials. Please try again.')
            return redirect(url_for('customer_login'))

    return render_template('customer_login.html')

# Customer Dashboard
@app.route('/customer_dashboard', methods=['GET'])
def customer_dashboard():
    customer_id = session.get('customer_id')  # Get the logged-in customer's ID
    if customer_id is None:
        flash('Please log in to access your dashboard.')
        return redirect(url_for('customer_login'))

    # Display available products for the customer
    products = Product.query.all()
    return render_template('customer_dashboard.html', products=products)

@app.route('/place_order/<int:product_id>', methods=['POST'])
def place_order(product_id):
    customer_id = session.get('customer_id')
    if customer_id is None:
        flash('Please log in to place an order.')
        return redirect(url_for('customer_login'))

    product = Product.query.get(product_id)
    if product is None:
        flash('Product not found.')
        return redirect(url_for('customer_dashboard'))

    try:
        ordered_quantity = int(request.form.get('quantity', 0))
    except ValueError:
        ordered_quantity = 0

    if ordered_quantity <= 0:
        flash('Please enter a valid quantity.')
        return redirect(url_for('customer_dashboard'))

    if ordered_quantity > product.quantity:
        flash('Requested quantity exceeds available stock.')
        return redirect(url_for('customer_dashboard'))

    product.quantity -= ordered_quantity
    new_order = Order(
        product_id=product.id,
        customer_id=customer_id,
        ordered_quantity=ordered_quantity,
        transport_status='Pending',
        transport_notes='Awaiting transport assignment.'
    )
    db.session.add(new_order)
    db.session.commit()

    flash('Order placed successfully! The farmer will receive an alert.')
    return redirect(url_for('customer_orders'))

@app.route('/update_transport/<int:order_id>', methods=['POST'])
def update_transport(order_id):
    farmer_id = session.get('farmer_id')
    if farmer_id is None:
        flash('Please log in to update transport details.')
        return redirect(url_for('farmer_login'))

    order = Order.query.get(order_id)
    if order is None or order.product.farmer_id != farmer_id:
        flash('Order not found or you do not have permission to modify it.')
        return redirect(url_for('farmer_orders'))

    transport_status = request.form.get('transport_status', 'Pending')
    transport_notes = request.form.get('transport_notes', '').strip()

    order.transport_status = transport_status
    order.transport_notes = transport_notes or 'No additional notes.'
    db.session.commit()

    flash('Transport information updated.')
    return redirect(url_for('farmer_orders'))

# Serve static files (for image files)
@app.route('/static/images/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Logout
@app.route('/logout', methods=['GET'])
def logout():
    session.clear()  # Clear session data
    flash('You have been logged out.')
    return redirect(url_for('home'))

# Error Handling
@app.errorhandler(404)
def not_found(e):
    return "<h1>Page not found</h1>", 404

@app.errorhandler(500)
def internal_error(e):
    return "<h1>Something went wrong</h1>", 500

if __name__ == '__main__':
    app.run(debug=True)
