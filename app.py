from flask import Flask, abort, render_template, render_template_string, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime 

app = Flask(__name__)
app.secret_key = "mysecret"

# Database setup (SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)

# Order model   
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    total = db.Column(db.Integer, nullable=False)
    items = db.Column(db.Text, nullable=False)        # e.g., "Formal Shirt (₹999), Denim Jeans (₹1299)"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Example product data
products = [
    {"id": 1, "name": "Casual Shirt", "price": 799,  "image": "blackshirt.jpeg",
     "popularity": 72, "created_at": datetime(2025, 8, 1)},
    {"id": 2, "name": "Formal Shirt", "price": 999,  "image": "maroonshirt.jpeg",
     "popularity": 95, "created_at": datetime(2025, 8, 18)},
    {"id": 3, "name": "Denim Jeans", "price": 1299, "image": "blackpant.jpeg",
     "popularity": 81, "created_at": datetime(2025, 8, 10)},
    {"id": 4, "name": "Chinos Pant", "price": 1199, "image": "greypant.jpeg",
     "popularity": 65, "created_at": datetime(2025, 8, 20)},
    {"id": 5, "name": "Casual T-Shirt", "price": 699,  "image": "BlackTshirt.jpg",
     "popularity": 75, "created_at": datetime(2025, 8, 2)},
    {"id": 6, "name": "Formal T-Shirt", "price": 899,  "image": "maroonTshirt.jpg",
     "popularity": 92, "created_at": datetime(2025, 8, 12)},
    {"id": 7, "name": "Denim cargo", "price": 1499, "image": "Blackcargo.jpg",
     "popularity": 84, "created_at": datetime(2025, 8, 15)},
    {"id": 8, "name": "Trousers", "price": 1299, "image": "Trousers.jpg",
     "popularity": 67, "created_at": datetime(2025, 8, 24)},
]

# Inject cart count globally
@app.context_processor
def inject_cart_count():
    cart_count = len(session.get("cart", []))
    return dict(cart_count=cart_count)

@app.route("/")
def home():
    if "user" not in session:
        return redirect(url_for("login"))

    sort = request.args.get("sort", "popularity")  # default
    items = products[:]  # copy

    if sort == "price_asc":
        items.sort(key=lambda x: x["price"])
    elif sort == "price_desc":
        items.sort(key=lambda x: x["price"], reverse=True)
    elif sort == "new":
        items.sort(key=lambda x: x["created_at"], reverse=True)
    else:  # "popularity"
        items.sort(key=lambda x: x["popularity"], reverse=True)

    return render_template("index.html",
                           products=items,
                           user=session["user"],
                           selected_sort=sort)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session["user"] = username
            session["cart"] = []
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Validate inputs
        if not username or not password:
            return render_template("register.html", error="Username and password are required.")

        # Check duplicates
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template("register.html", error="Username already exists")

        # Create user
        try:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Show a friendly error and DO return
            return render_template("register.html", error="Could not create user. Please try again.")

        # Always return/redirect after POST
        return redirect(url_for("login"))

    # GET must also return
    return render_template("register.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/add_to_cart/<int:product_id>", methods=["POST", "GET"])
def add_to_cart(product_id):
    # Optional: validate product exists
    if not any(p["id"] == product_id for p in products):
        return redirect(url_for("home"))

    cart = session.get("cart", [])
    cart.append(product_id)
    session["cart"] = cart        # reassign so Flask detects change
    # or: session.modified = True
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    if "cart" not in session:
        session["cart"] = []
    cart_items = [p for p in products if p["id"] in session["cart"]]
    total = sum(item["price"] for item in cart_items)
    return render_template("cart.html", cart=cart_items, total=total)

@app.route("/remove_from_cart/<int:product_id>")
def remove_from_cart(product_id):
    if "cart" in session and product_id in session["cart"]:
        session["cart"].remove(product_id)
    return redirect(url_for("cart"))

@app.route("/buy_now", methods=["POST"])
def buy_now():
    # must be logged in
    if "user" not in session:
        return redirect(url_for("login"))

    cart_ids = session.get("cart", [])
    # Build items list the same way you render the cart
    cart_items = [p for p in products if p["id"] in cart_ids]
    if not cart_items:
        # nothing to buy
        return redirect(url_for("cart"))

    total = sum(item["price"] for item in cart_items)
    items_text = ", ".join([f'{i["name"]} (₹{i["price"]})' for i in cart_items])

    # create order
    order = Order(username=session["user"], total=total, items=items_text)
    db.session.add(order)
    db.session.commit()

    # clear cart
    session["cart"] = []

    # go to success page
    return redirect(url_for("order_success", order_id=order.id))


@app.route("/order_success/<int:order_id>")
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template("order_success.html", order=order)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)