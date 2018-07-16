import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    #Initialize stotal
    stotal = 0

    #Selecting the users portfolio
    portfolio_stocks = db.execute("SELECT stock_symbol, stock_count FROM portfolio WHERE user_id = :uid", \
    uid = session["user_id"])

    #Update the stock information
    for portfolio_stock in portfolio_stocks:
        symbol = portfolio_stock["stock_symbol"]
        shares = portfolio_stock["stock_count"]
        stock = lookup(symbol)
        price = stock["price"]
        total = price * shares
        price = usd(price)
        stotal += total

        db.execute("UPDATE portfolio SET stock_price = :sprice, total = :utotal \
        WHERE user_id = :uid AND stock_symbol = :ssymbol", sprice = price, utotal = usd(total), \
        uid = session["user_id"], ssymbol = symbol)

    #Get updated stocks
    updated_stocks = db.execute("SELECT * FROM portfolio WHERE user_id = :uid", uid = session["user_id"])

    #Get users cash
    scash = db.execute("SELECT cash FROM users WHERE id = :uid", uid = session["user_id"])

    #Update the total
    stotal += scash[0]["cash"]
    stotal = usd(stotal)


    return render_template("index.html",stocks = updated_stocks, cash = usd(scash[0]["cash"]), total = stotal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    #Check if POST
    if request.method == "POST":

        #Check the symbol
        if not request.form.get("symbol"):
            return apology("Please enter the symbol!")

        #Check number of shares
        if not request.form.get("shares"):
            return apology("Please enter a valid number of shares!")

        #Testing
        test_num = float(request.form.get("shares"))

        try:
            if int(test_num)<1:
                return apology("Please enter a valid number of shares!")

        except:
            return apology("Please enter a valid number of shares!")

        #Check for validity of stock
        #BUG: Lookup often returns a null value for a valid stock. Look for possble replacements
        if not lookup(request.form.get("symbol")):
            return apology("Invalid stock")

        #Stock lookup
        stock = lookup(request.form.get("symbol"))
        nos = int(request.form.get("shares"))

        #Check if user has enough cash
        money = db.execute("SELECT cash FROM users WHERE id = :uid", uid=session["user_id"])
        if not money or float(money[0]["cash"]) < stock["price"] * nos:
            return apology("Not enough cash!")

        #Insert into history
        db.execute("INSERT INTO history (user_id, stock_symbol, stock_number, type, price) \
        VALUES (:uid, :symbol, :snum, 'BUY', :sprice)",uid=session["user_id"], symbol = stock["symbol"], \
        snum=nos, sprice = usd(stock["price"]))

        #Debit the amount
        db.execute("UPDATE users SET cash = cash - :cost WHERE id = :uid", \
        cost = usd(stock["price"])*nos, uid=session["user_id"])

        #Check for existing shares
        result = db.execute("SELECT stock_count FROM portfolio WHERE user_id = :uid AND stock_symbol = :symbol", \
        uid = session["user_id"], symbol = stock["symbol"])

        #Insert if none pre-existing
        if not result:
            db.execute("INSERT INTO portfolio (user_id, stock_symbol, stock_count) VALUES (:uid, :symbol, :count)", \
            uid = session["user_id"], symbol = stock["symbol"], count = nos)

        #Update if pre-existing
        else:
            db.execute("UPDATE portfolio SET stock_count = stock_count + :count WHERE user_id = :uid \
            AND stock_symbol = :symbol", count = nos, uid = session["user_id"], symbol = stock["symbol"])

        #Return to index
        return redirect("/")

    #Reload if not POST
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    #Get transactions
    transaction_list = db.execute("SELECT * FROM history WHERE user_id = :uid", uid = session["user_id"])

    return render_template("history.html", stocks =transaction_list)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    #Check if POST
    if request.method == "POST":

        #Check if form was filled
        if not request.form.get("symbol"):
            return apology("Please enter a symbol!")

        #Check for valid input
        if not lookup(request.form.get("symbol")):
            return apology("Stock not found!")

        #Lookup the stock
        s = lookup(request.form.get("symbol"))
        sprice = usd(s["price"])

        #Display the stock
        return render_template("quoted.html", stock=s, price=sprice)

    #Reload if not POST
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register User"""

    #Check if POST
    if request.method == "POST":

        #Check for username
        if not request.form.get("username"):
            return apology("Please enter a username!")

        #Check for Password
        if not request.form.get("password"):
            return apology("Please enter a password!")

        #Check for Password Confirm
        if not request.form.get("confirmation"):
            return apology("Please enter a confirmation password")

        #Check if passwords match
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("Passwords don't match!")

        #Add the user to the database
        result = db.execute("INSERT INTO users (username, hash) VALUES( :username, :hash)", \
        username = request.form.get("username"), \
        hash = generate_password_hash(request.form.get("password")))

        #Check if username not unique
        if not result:
            return apology("Username not unique!")

        #Store session
        session["user_id"] = result

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Settings"""

    #Check if POST
    if request.method == "POST":

        #Check for Password
        if not request.form.get("password"):
            return apology("Please enter a password!")

        #Check for Password Confirm
        if not request.form.get("confirmation"):
            return apology("Please enter a confirmation password")

        #Check if passwords match
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("Passwords don't match!")

        #Add the user to the database
        db.execute("UPDATE users SET hash = :pwd WHERE id = :uid", \
        uid = session["user_id"], \
        pwd = generate_password_hash(request.form.get("password")))

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("settings.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    #Check if POST
    if request.method == "POST":

        #Get the symbol
        symbol = request.form.get("symbol")

        #Get the number of shares
        shares = int(request.form.get("shares"))

        #Check if input exists
        if not shares or shares < 1:
            return apology("Invalid number of shares!")

        #Retrieve the quantity of the user's stock
        stock = db.execute("SELECT stock_count FROM portfolio WHERE user_id = :uid AND stock_symbol = :ssymbol", \
        uid = session["user_id"], ssymbol = symbol)

        #Check if user has enough stock
        if stock[0]["stock_count"] < shares:
            return apology("Not enough stock!")

        #Lookup the current price
        price = lookup(symbol)

        #Amount to be added to the user's account
        amt = price["price"] * shares

        #Add the amount to the account
        db.execute("UPDATE users SET cash = cash + :windfall WHERE id = :uid", windfall = amt, uid = session["user_id"])

        #Reduce the stock held
        db.execute("UPDATE portfolio SET stock_count = stock_count - :sold \
        WHERE user_id = :uid AND stock_symbol = :ssymbol", sold = shares, uid = session["user_id"], ssymbol = symbol)

        #Update history
        db.execute("INSERT INTO history (user_id, stock_symbol, stock_number, type, price) \
        VALUES (:uid, :ssymbol, :snum, 'SELL', :sprice)",uid=session["user_id"], \
        ssymbol = symbol, snum=shares, sprice = usd(price["price"]))

        #Return to index

        return redirect("/")


    #Render sell if not POST
    else:
        stocks = db.execute("SELECT stock_symbol FROM portfolio WHERE user_id = :uid", uid = session["user_id"])
        return render_template("sell.html",options=stocks)



def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
