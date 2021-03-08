import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd


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
app.jinja_env.filters["lookup"] = lookup

# Configure session to use filesystem (instead of signed cookies)
# app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = get_portfolio()
    cash = get_cash()
    all_stock = get_total_stock()
    total = cash + all_stock
    return render_template("index.html", rows=rows, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via GET
    if request.method == "GET":
        return render_template("buy.html")
    
    else:
        # Ensure fields are not NULL
        symbol = request.form.get("symbol")
        shares = request.form.get("shares", type=int)
        if not symbol:
            return apology("must provide stock symbol", 400)
        elif not shares:
            return apology("how many shares do you want to buy?", 400)
        # Ensure the stock symbol exists
        elif lookup(symbol) == None:
            return apology("sorry, stock not found", 400)
        elif shares < 1 or isinstance(shares, int) == False:
            return apology("number of shares must be positive integer", 400)
        else:
            company = lookup(symbol)["name"]
            price = lookup(symbol)["price"]
            cash = get_cash()
            # Ensure user has enough cash
            if cash < price * shares:
                return apology("sorry, not enough cash", 400)
            else:
                # Insert purchased stock
                update_cash(cash, price, shares)
                trade(symbol.upper(), company, price, shares)
                
            flash("Successfully purchased stock(s)!")
            return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", rows=rows)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    flash("Logged out")
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    # User reached route via GET
    if request.method == "GET":
        return render_template("quote.html")
        
    else:
        if lookup(request.form.get("symbol")) == None:
            return apology("sorry, stock not found", 400)
        else:
            stock = lookup(request.form.get("symbol"))
            return render_template("price.html", stock=stock)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "GET":
        return render_template("register.html")
    
    else:
        # Ensure fields are not NULL
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        
        # Ensure password is the same as confirmation
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)
        else:
            # Ensure the username does not exisit
            rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
            if len(rows) > 0:
                return apology("username already exisits", 400)
    
            else:
                # Insert new user to database
                user_id = db.execute("INSERT INTO users (username, hash) VALUES(?,?)", request.form.get(
                    "username"), generate_password_hash(request.form.get("confirmation")))
                session["user_id"] = user_id
                # Redirect user to home page
                flash('Successfully registered and logged in!')
                return redirect("/")
        

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
    if request.method == "GET":
        rows = get_portfolio()
        return render_template("sell.html", rows=rows)
    
    else:
        # Ensure fields are not empty or wrong
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        if not symbol:
            return apology("must provide stock symbol", 400)
        elif not shares:
            return apology("how many shares do you want to sell?", 400)
        elif shares < 1 or isinstance(shares, int) == False:
            return apology("number of shares must be positive integer", 400)
            
        else:
            holding = get_stock(symbol)[0]["sum_shares"]
            if holding < shares:
                return apology("not enough shares to sell", 400)
            else:
                company = get_stock(symbol)[0]["company"]
                price = lookup(symbol)["price"]
                cash = get_cash()
                update_cash(cash, price, shares * -1)
                trade(symbol.upper(), company, price, shares * -1)
                flash("Successfully sold stock(s)!")
                return redirect("/")


@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """Buy shares of stock"""
    # User reached route via GET
    if request.method == "GET":
        return render_template("cash.html")
    else:
        if not request.form.get("cash"):
            return apology("how much money do you want?", 400)
        elif int(request.form.get("cash")) < 1 or int(request.form.get("cash")) > 99999 or isinstance(int(request.form.get("cash")), int) == False:
            return apology("you can only get $1 to $99999 each time", 400)
        else:
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", int(request.form.get("cash")), session["user_id"])
            flash("KA-CHING $$$$$$$$$$$$")
            return redirect("/")
            

@login_required
def get_cash():
    return db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]


@login_required
def get_portfolio():
    return db.execute("SELECT *, SUM(shares) AS sum_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING sum_shares > 0",
                      session["user_id"])


@login_required
def get_stock(symbol):
    return db.execute("SELECT symbol, company, SUM(shares) AS sum_shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol",
                      session["user_id"], symbol)


@login_required
def get_total_stock():
    rows = get_portfolio()
    all_stock = 0
    for row in rows:
        all_stock += row["sum_shares"] * lookup(row["symbol"])["price"]
    return all_stock


@login_required
def trade(symbol, company, price, shares):
    return db.execute("INSERT INTO transactions (user_id, symbol, company, price, shares, trade_size) VALUES(?,?,?,?,?,?)", session["user_id"],
                      symbol, company, price, shares, price * shares)


@login_required
def update_cash(cash, price, shares):
    return db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - price * shares, session["user_id"])
            

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
