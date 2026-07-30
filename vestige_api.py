from pydantic import BaseModel, Field
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from typing import Annotated
import mysql.connector

# Reminder
# This is just a reference code on how the gallery website will work
# The following is an API

# Stores the html pages
templates = Jinja2Templates(directory="html_pages")
templates_2 = Jinja2Templates(directory="html_pages/user_pages")

# For initiating an api
app = FastAPI()

# The structure of the data for the signup page
class User(BaseModel):
    first_name: Annotated[str, Field(min_length=5, max_length=8)]
    last_name: Annotated[str, Field(min_length=5, max_length=8)]
    email: str
    password: str
    age: Annotated[int, Field(ge=18, le=90)]
    country: str

# For connecting to the database
def connect_to_db():
    return mysql.connector.connect(
           host="127.0.0.1",
           user="root",
           password="pass123",
           database="vestige_db"
        )

# Homepage
@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="homepage.html"
    )

# Users will create their accounts in this endpoint
@app.get("/signup")
def account_signup(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="sign_up.html"
    )

@app.post("/signup", response_class=HTMLResponse)
def account_creation(user: Annotated[User, Form()], request: Request):
    try:
        db = connect_to_db()
        cursor = db.cursor()
        query = "INSERT INTO users (first_name, last_name, email, password, age, country) VALUES (%s, %s, %s, %s, %s, %s)"
        data = (
            user.first_name,
            user.last_name,
            user.email,
            user.password,
            user.age,
            user.country
        )
        cursor.execute(query, data)
        cursor.close()
        db.commit()
        return templates_2.TemplateResponse(
            request=request,
            name="home.html",
            context={"first_name": user.first_name}
        )
    
    except Exception as e:
            return {"error": f"{e}"}
    
    finally:
        cursor.close()
        db.close()

# Shows the login page
@app.get("/login", response_class=HTMLResponse)
def account_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="log_in.html"
    )

# For gathering information from the user
@app.post("/login", response_class=HTMLResponse)
def account_login(request: Request, email: Annotated[str, Form()], password: Annotated[str, Form()]):
    try:
        db = connect_to_db()
        cursor = db.cursor(dictionary=True)
        query = ("SELECT first_name, last_name, email, password FROM users WHERE email = %s AND password = %s")
        data = (email, password)
        cursor.execute(query, data)
        user = cursor.fetchone()
        if user is None:
            return templates.TemplateResponse(
                request=request,
                name="log_in.html",
                context={"error": "Incorrect email or password"}
            )

        elif password != user["password"]:
            return templates.TemplateResponse(
                request=request,
                name="log_in.html",
                context={"error": "Incorrect email or password"}
            )

        elif email == user["email"] and password != user["password"]:
            return templates.TemplateResponse(
                request=request,
                name="log_in.html",
                context={"error": "Incorrect email or password"}
            )

        return templates_2.TemplateResponse(
            request=request,
            name="home.html",
            context={"first_name": user["first_name"]}
        )

    except Exception as e:
        return {"error": f"{e}"}

    finally:
        cursor.close()
        db.close()


