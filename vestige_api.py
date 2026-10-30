from pydantic import BaseModel, Field
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from typing import Annotated
from database.db_connection import connect_to_db
from security.token_hash import hashed_token_generate
import mysql.connector
from prometheus_client import Counter, generate_latest
import string
import random
import hashlib
import os
import time

# Used for storing mertics or user data
requests_data = Counter(
    "fastapi_requests_total",
    "Total number of requests"
)

# Stores the html pages
templates = Jinja2Templates(directory="html_pages")
templates_2 = Jinja2Templates(directory="html_pages/user_pages")

# For initiating an api
app = FastAPI()

# For fetching pictures and css design
app.mount("/css_design", StaticFiles(directory="css_design"), name="css")
app.mount("/html_pages/pictures", StaticFiles(directory="html_pages/pictures"), name="picture")



# The structure of the data for the signup page
class User(BaseModel):
    first_name: Annotated[str, Field(min_length=3, max_length=8)]
    last_name: Annotated[str, Field(min_length=3, max_length=8)]
    email: str
    password: str
    age: Annotated[int, Field(ge=18, le=90)]
    country: str
    reference_id: str | None = None

class Contact(BaseModel):
    first_name: Annotated[str, Field(min_length=3)]
    last_name: Annotated[str, Field(min_length=3)]
    email: Annotated[str, Field(min_length=10)]
    contact_number: Annotated[int, Field(ge=1000000000)]

# Collects user metrics then stores them then sneds to the grafana client
# Optional to install grafana client but recommended
@app.get("/metrics")
def metrics():
    # Returns a default web response
    return Response(
        generate_latest(), # Shows the latest user metrics
        media_type="text/plain" # To be sent as a text type
    )

@app.get("/")
async def redirect_to_home(request: Request):
    requests_data.inc()
    data = request.cookies.get("__Host-session")
    if data:
        return RedirectResponse(
            url="/user_home",
            status_code=303
        )

    return RedirectResponse(
        url="/home",
        status_code=303
    )

@app.get("/user_home", response_class=HTMLResponse)
async def user_homepage(request: Request):
    requests_data.inc()
    try:
        db = connect_to_db()
        cursor = db.cursor(dictionary=True, buffered=True)
        query = "SELECT * FROM users where session_id = %s"
        data = request.cookies.get("session_id")
        cursor.execute(query, (data,))
        user = cursor.fetchone()
        if user:
            return RedirectResponse(
                url="/user_home",
                status_code=303
            )

        return RedirectResponse(
            url="/home",
            status_code=303
        )

    except Exception as e:
        raise

    finally:
        cursor.close()
        db.close()
        

# Homepage
@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    requests_data.inc()
    return templates.TemplateResponse(
        request=request,
        name="homepage.html"
    )

#About
@app.get("/about")
async def about(request: Request):
    requests_data.inc()
    return templates.TemplateResponse(
        request=request,
        name="about.html"
    )

#Contact
@app.get("/contact/v1")
async def contact(request: Request):
    requests_data.inc()
    return templates.TemplateResponse(
        request=request,
        name="contact.html"
    )

@app.post("/contact/v1", response_class=HTMLResponse)
async def contact(contact_data: Annotated[Contact, Form()], request: Request):
    requests_data.inc()
    try:
        db = connect_to_db()
        cursor = db.cursor()
        query = "INSERT INTO contacts (first_name, last_name, email, contact_number) VALUES (%s, %s, %s, %s)"
        data = (
            contact_data.first_name, 
            contact_data.last_name, 
            contact_data.email, 
            contact_data.contact_number
            )
        cursor.execute(query, data)
        return templates.TemplateResponse(
            request=request,
            name="contact.html",
            context={"sent_message": "Information sent successfully"}
        )
    
    except Exception as e:
        raise

    finally:
        cursor.close()
        db.commit()
        db.close()

# Users will create their accounts in this endpoint
@app.get("/register/v1")
async def account_signup(request: Request):
    requests_data.inc()
    return templates.TemplateResponse(
        request=request,
        name="sign_up.html"
    )

@app.post("/register/v1", response_class=HTMLResponse)
async def account_creation(user: Annotated[User, Form()], request: Request, response: Response):
    requests_data.inc()
    try:
        db = connect_to_db()
        cursor = db.cursor()
        query = "INSERT INTO users (tenant_id, first_name, last_name, email, password, age, country, reference_id, session_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        user.reference_id = f"{"".join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=15))}"

        data = (
            random.choice([1, 2, 3]),
            user.first_name,
            user.last_name,
            user.email,
            user.password,
            user.age,
            user.country,
            user.reference_id,
            hashed_token_generate
        )

        cursor.execute(query, data)

        success_response = RedirectResponse(
            url="/user_home",
            status_code=303
        )

        success_response.set_cookie(
            key="__Host-session",
            value=hashed_token_generate(),
            path="/",
            samesite="lax"
        )

        return success_response
    
    except Exception as e:
            raise

    finally:
        cursor.close()
        db.commit()
        db.close()