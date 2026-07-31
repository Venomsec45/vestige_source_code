import mysql.connector

def connect_to_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="Mike",
        password="pass123",
        database="vestige_db"    
    )
