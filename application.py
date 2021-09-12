import os
# export API_KEY=pk_758e7da491d74eaeaf2121345cde7e65
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

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
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
    if request.method == "GET":
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        data = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
        total = 0
        for stock in data:
            price = lookup(stock["symbol"])["price"]
            stock["price"] = price
            stock["name"] = lookup(stock["symbol"])["name"]
            stock['total'] = stock['shares']*price
            total += stock["shares"]*price

        cash = cash[0]["cash"]
    # print(total)
    return render_template("index.html", data=data, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        sym = request.form.get("symbol")
        data = lookup(sym)
        total = 0
        if not data:
            return apology("incorrect arguments")
        price = usd(data["price"])
        shares = request.form.get("shares")
        user_id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        stocks = db.execute("SELECT * FROM transactions WHERE user_id = ?", user_id)
        if not shares.isnumeric():
            return apology("must provide int", 400)
        if int(shares) < 1:
            return apology("must provide valid value > 0", 400)

        if float(cash[0]["cash"]) >= total and int(shares) > 0:
            total = float(data["price"]) * int(shares)
            if db.execute("SELECT symbol FROM transactions WHERE user_id = ? AND symbol = ?", user_id, "C") == []:
                db.execute("INSERT INTO transactions (symbol, shares, price, user_id) VALUES (?, ?, ?, ?)",
                           data["symbol"], shares, price, user_id)
            else:
                db.execute("UPDATE transactions SET shares = shares + ?  WHERE symbol = ? AND user_id = ?",
                           shares, data["symbol"], user_id)
            db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", total, user_id)
            db.execute("INSERT INTO records (symbol, shares, price, type, user_id) VALUES (?, ?, ?, ?, ?)",
                       data["symbol"], shares, data["price"], "buy", session["user_id"])
            return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    data = db.execute("SELECT * FROM records WHERE user_id = ?", session["user_id"])
    return render_template("history.html", data=data)


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
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        result = lookup(symbol)
        print(result)
        if result == None or symbol == " ":
            return apology("must provide valid symbol", 400)
        return render_template("quote.html", result=result)
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    username = request.form.get("username")
    password = request.form.get("password")
    check_password = request.form.get("confirmation")

    if request.method == "POST":
        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)

        # Ensure password was submitted
        elif not check_password:
            return apology("must confirm password", 400)

        # handle duplicates
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) != 0:
            return apology("username existent", 400)

        if password == check_password:
            hash_pass = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash_pass)
            user_id = db.execute("SELECT id FROM users WHERE username = ? AND hash = ?", username, hash_pass)
            print(user_id)
            # remember user logged in
            session["user_id"] = user_id[0]["id"]
            return redirect("/")
        else:
            return apology("must match password", 400)

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    print(stocks)
    if request.method == "POST":
        if not request.form.get("shares"):
            return apology("missing arguments", 400)
        shares = request.form.get("shares")
        symbol = request.form.get("symbol")
        user_shares = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)
        print(user_shares[0]["shares"])
        print(shares)
        if int(shares) > user_shares[0]["shares"]:
            return apology("not enough shares", 400)
        else:
            current_price = lookup(symbol)
            current_price = current_price["price"]
            # ammount to be added to user balance
            total_amount = current_price * int(shares)

            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", total_amount, session["user_id"])

            db.execute("UPDATE transactions SET shares = shares - ? WHERE user_id = ? AND symbol = ?",
                       shares, session["user_id"], symbol)

            current_shares = db.execute(
                "SELECT shares FROM transactions WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)

            # delete if less than 1 share
            if current_shares[0]["shares"] < 1:
                db.execute("DELETE FROM transactions WHERE shares < 1 AND user_id = ? AND symbol = ?", session["user_id"], symbol)

            # keep track of transactions
            shares = 0 - int(shares)
            db.execute("INSERT INTO records (symbol, shares, price, type, user_id) VALUES (?, ?, ?, ?, ?)",
                       symbol, shares, current_price, "sold", session["user_id"])
            return redirect("/")
    return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
