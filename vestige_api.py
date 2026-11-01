# Third party libraries
from pydantic import BaseModel, Field, EmailStr
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime as dt, timedelta, timezone
from typing import Annotated
from prometheus_client import Counter, generate_latest
import mysql.connector

# Libraries from a module
from database.db_connection import connect_to_db
from security.hash_token import hashed_token_generate
from security.password_sha256_hash import hash_256_password

# Standard libraries
from pathlib import Path
import hmac
import secrets
import string

# Resolve paths relative to this file so the app works no matter which
# directory the server is started from
BASE_DIR = Path(__file__).resolve().parent

SESSION_COOKIE = "session_id"
SESSION_LIFETIME = timedelta(days=1)

# Used for storing metrics or user data
requests_data = Counter(
    "fastapi_requests_total",
    "Total number of requests"
)

# Stores the html pages
templates = Jinja2Templates(directory=BASE_DIR / "html_pages")
templates_2 = Jinja2Templates(directory=BASE_DIR / "html_pages" / "user_pages")

# For initiating an api
app = FastAPI()

# For fetching pictures and css design
app.mount("/css_design", StaticFiles(directory=BASE_DIR / "css_design"), name="css")
app.mount("/html_pages/pictures", StaticFiles(directory=BASE_DIR / "html_pages" / "pictures"), name="picture")


# The structure of the data for the signup page
class User(BaseModel):
    first_name: Annotated[str, Field(min_length=3, max_length=8)]
    last_name: Annotated[str, Field(min_length=3, max_length=8)]
    email: EmailStr
    password: Annotated[str, Field(min_length=8)]
    age: Annotated[int, Field(ge=18, le=90)]
    country: str


class Contact(BaseModel):
    first_name: Annotated[str, Field(min_length=3)]
    last_name: Annotated[str, Field(min_length=3)]
    email: EmailStr
    contact_number: Annotated[int, Field(ge=1000000000)]


def expiration_date() -> str:
    future_day = dt.now(timezone.utc) + SESSION_LIFETIME
    return future_day.strftime("%Y-%m-%d %H:%M:%S")


def generate_reference_id(length: int = 15) -> str:
    # secrets (not random) so IDs can't be predicted
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        path="/",
        samesite="lax",
        httponly=True,  # JavaScript can't read the session cookie
        max_age=int(SESSION_LIFETIME.total_seconds()),
        # Set secure=True once the site is served over HTTPS
    )


# Collects user metrics then stores them then sends to the grafana client
# Optional to install grafana client but recommended
@app.get("/metrics")
def metrics():
    return Response(
        generate_latest(),
        media_type="text/plain"
    )


@app.get("/")
def redirection():
    return RedirectResponse(url="/home", status_code=303)


# Plain "def" (not "async def") for routes that use the blocking MySQL
# driver, so FastAPI runs them in a thread pool instead of freezing the server
@app.get("/user_home", response_class=HTMLResponse)
def user_homepage(request: Request):
    requests_data.inc()
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        return RedirectResponse(url="/home", status_code=303)

    db = connect_to_db()
    cursor = db.cursor(dictionary=True, buffered=True)
    try:
        query = "SELECT first_name, reference_id, expires_at FROM users WHERE session_id = %s"
        cursor.execute(query, (session_token,))
        user = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    # Only let the user in while the session has NOT expired yet
    if user and user["expires_at"] and user["expires_at"].replace(tzinfo=timezone.utc) > dt.now(timezone.utc):
        return templates_2.TemplateResponse(
            request=request,
            name="home.html",
            context={"first_name": user["first_name"], "hash_num": user["reference_id"]}
        )

    return RedirectResponse(url="/home", status_code=303)


# Homepage
@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    requests_data.inc()
    return templates.TemplateResponse(request=request, name="homepage.html")


# About
@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    requests_data.inc()
    return templates.TemplateResponse(request=request, name="about.html")


# Contact
@app.get("/contact/v1", response_class=HTMLResponse)
async def contact_page(request: Request):
    requests_data.inc()
    return templates.TemplateResponse(request=request, name="contact.html")


@app.post("/contact/v1", response_class=HTMLResponse)
def contact_submit(contact_data: Annotated[Contact, Form()], request: Request):
    requests_data.inc()
    db = connect_to_db()
    cursor = db.cursor()
    try:
        query = "INSERT INTO contacts (first_name, last_name, email, contact_number) VALUES (%s, %s, %s, %s)"
        data = (
            contact_data.first_name,
            contact_data.last_name,
            contact_data.email,
            contact_data.contact_number
        )
        cursor.execute(query, data)
        db.commit()  # Only commit when the insert succeeded
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return templates.TemplateResponse(
        request=request,
        name="contact.html",
        context={"sent_message": "Information sent successfully"}
    )


# Users will create their accounts in this endpoint
@app.get("/signup/v1", response_class=HTMLResponse)
async def signup_page(request: Request):
    requests_data.inc()
    return templates.TemplateResponse(request=request, name="sign_up.html")


@app.post("/signup/v1", response_class=HTMLResponse)
def signup_submit(user: Annotated[User, Form()], request: Request):
    requests_data.inc()
    # A fresh session token for every user (never shared between users)
    session_token = hashed_token_generate()

    db = connect_to_db()
    cursor = db.cursor()
    try:
        query = "INSERT INTO users (tenant_id, first_name, last_name, email, password, age, country, reference_id, session_id, expires_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        data = (
            secrets.choice([1, 2, 3]),
            user.first_name,
            user.last_name,
            user.email,
            hash_256_password(user.password),
            user.age,
            user.country,
            generate_reference_id(),
            session_token,
            expiration_date()
        )
        cursor.execute(query, data)
        db.commit()
    except mysql.connector.IntegrityError:
        # e.g. the email is already registered (if the column is UNIQUE)
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="sign_up.html",
            context={"error": "An account with that email already exists"},
            status_code=400
        )
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    success_response = RedirectResponse(url="/user_home", status_code=303)
    set_session_cookie(success_response, session_token)
    return success_response


# Shows the login page
@app.get("/login/v1", response_class=HTMLResponse)
async def login_page(request: Request):
    requests_data.inc()
    return templates.TemplateResponse(request=request, name="log_in.html")


# For gathering information from the user
@app.post("/login/v1", response_class=HTMLResponse)
def login_submit(request: Request, email: str = Form(), password: str = Form()):
    requests_data.inc()
    login_failed = templates.TemplateResponse(
        request=request,
        name="log_in.html",
        context={"error": "Incorrect email or password"},
        status_code=401
    )

    db = connect_to_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT email, password FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        # Constant-time comparison so response timing doesn't leak hash info
        if user is None or not hmac.compare_digest(hash_256_password(password), user["password"]):
            return login_failed

        # New token on every login so an old/stolen cookie stops working
        session_token = hashed_token_generate()
        cursor.execute(
            "UPDATE users SET session_id = %s, expires_at = %s WHERE email = %s",
            (session_token, expiration_date(), user["email"])
        )
        db.commit()  # Without this the new session was never saved
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    success_response = RedirectResponse(url="/user_home", status_code=303)
    # The cookie must go on the response that is actually returned
    set_session_cookie(success_response, session_token)
    return success_response
