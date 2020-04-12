import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

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
    tabledata = db.execute("SELECT symbol, shares FROM ledger WHERE user_id = :user_id", user_id=session["user_id"])
    tablelength = len(tabledata)
    # combine duplicates
    for i in range(0,tablelength - 1):
        for j in range(i + 1, tablelength):
            if tabledata[i]["symbol"] == tabledata[j]["symbol"]:
                tabledata[i]["shares"] += tabledata[j]["shares"]
    # count how many times each name shows up
    countertable={}
    for slot in range(len(tabledata)):
        symbolkey = str(tabledata[slot]["symbol"])
        if countertable.get(symbolkey) == None:
             countertable[symbolkey] = 1
        else:
            countertable[symbolkey] += 1

    #delete the duplicate entries
    tabledata.reverse()
    tablekeys = list(countertable.keys())
    for symbcounter in range(len(tablekeys)):
        for delcounter in range(0,countertable[tablekeys[symbcounter]] - 1):
            for i in range(len(tabledata)):
                if tabledata[i]["symbol"] == tablekeys[symbcounter]:
                    del tabledata[i]
                    break
    #return render_template("debug.html", debugvar=countertable)


    cashtotal = 0
    for row in tabledata:
        stockinfo = lookup(row["symbol"])
        row["name"] = stockinfo["name"]
        row["price"] = stockinfo["price"]
        row["total"] = row["shares"] * row["price"]
        cashtotal = cashtotal + row["total"]
        row["total"]=usd(row["total"])
    
    cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
    cashtotal = usd(cashtotal + cash[0]["cash"])
    return render_template("index.html", tabledata=tabledata, cash=usd(cash[0]["cash"]), cashtotal=cashtotal)
    return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # load page to purchase
    if request.method == "GET":
        return render_template("buy.html")
    
    # get info
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        # test for blanks
        if not symbol:
            return apology("You must provide a symbol.")
        if not shares or shares <= 0:
            return apology("You must provide a positive amount of shares to purchase.")
        
        # pull stock info
        stockinfo = lookup(symbol)
        # test to see if symbol is valid
        if not stockinfo:
            return apology("Symbol provided does not exist.")

        # test for affordability
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id;", user_id = session["user_id"])
        #return render_template("debug.html", debugvar=cash)
        if (stockinfo['price'] * shares) > cash[0]['cash']:
            return apology("You cannot afford to purchase these stock(s).")
        
        # subtract cost from cash
        newcash = cash[0]['cash'] - (stockinfo['price'] * shares)
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id;", cash = newcash, user_id = session["user_id"])

        # add transaction to ledger
        db.execute("INSERT INTO ledger (symbol, user_id, shares, price, time) VALUES (:symbol, :user_id, :shares, :price, :time)", symbol=symbol, user_id=session["user_id"], shares=shares, price=stockinfo['price'], time= datetime.now())
        
        return redirect("/")
    return apology("TODO")


@app.route("/history")
@login_required
def history():
    transactiondata = db.execute("SELECT symbol, shares, price, time FROM ledger WHERE user_id = :user_id", user_id=session["user_id"])
    transactiondata.reverse()
    return render_template("history.html", transactiondata = transactiondata)
    """Show history of transactions"""
    return apology("TODO")


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
    if request.method == "GET":
        return render_template("quote.html")
    
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("You must provide a symbol.")
        
        quote = lookup(symbol)
        if quote == None:
            return apology("The symbol you entered does not exist.")
        
        return render_template("quoted.html", name = quote['name'], symbol = quote['symbol'], price = usd(quote['price']))


    """Get stock quote."""
    return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    # loads registration page
    if request.method == "GET":
        return render_template("register.html")
    
    # once user submits
    if request.method == "POST":
        # load inputs into vars
        username = request.form.get("username")
        pw = request.form.get("password")
        pc = request.form.get("confirmation")

        # Check for empty or mismatched entries
        if not username:
            return apology("You must provide a username!")
        if not pw:
            return apology("You must provide a password!")
        if not pc:
            return apology("You must confirm your password!")
        if pw != pc:
            return apology("Your passwords do not match.")
        
        # check if password has a letter, number, and symbol
        # no number
        if any(char.isdigit() for char in pw) == False:
            return apology("Your password must contain at least one number")
        # no symbol
        if any(not c.isalnum() and c !=' ' for c in pw) == False:
            return apology("Your password must contain at least one special character")
        #check if username already exists
        usernames = db.execute("SELECT username FROM users")
        for row in usernames:
            if username == row['username']:
                return apology("Username is taken.")
        
        # hash the pw
        pwhash = generate_password_hash(pw)
        # insert user into SQL
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :pwhash)", username=username, pwhash=pwhash)
        #redirect to homepage
        return redirect("/")

    """Register user"""
    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        options = db.execute("SELECT DISTINCT symbol FROM ledger WHERE user_id = :user_id", user_id=session["user_id"])
        return render_template("sell.html", menuoptions = options)
    
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not shares or shares <= 0:
            return apology("You must sell a positive amount of shares.")
        
        sharesowned = db.execute("SELECT SUM(shares) AS sum FROM ledger WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"], symbol=symbol)

        if sharesowned[0]['sum'] < shares:
            return apology("You cannot sell more shares than you own.")

        # get cashval
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id;", user_id = session["user_id"])
        

        stockinfo = lookup(symbol)

        newcash = cash[0]['cash'] + (stockinfo['price'] * shares)

        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id;", cash = newcash, user_id = session["user_id"])

        db.execute("INSERT INTO ledger (symbol, user_id, shares, price, time) VALUES (:symbol, :user_id, :shares, :price, :time)", symbol=symbol, user_id=session["user_id"], shares= 0 - shares, price=stockinfo['price'], time= datetime.now())
        return redirect("/")
        



        
    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
