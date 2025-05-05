import pandas as pd
import requests
import sqlite3
import streamlit as st
import urllib.parse
from io import StringIO, BytesIO
from geopy.geocoders import Nominatim
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# ----------------- DATABASE & FILE PATH SETUP -----------------
DB_FILE = "vaccination_data.db"
USER_DB = "users.db"

# ----------------- GOOGLE DRIVE FILE IDS -----------------
# File 1: Google Sheet
sheet_id = "1hJEb7aMjrD-EfAoN9jdhwBK2m9o0U-mh"
sheet_name = "not_vaccinated_analysis (3)"
encoded_sheet_name = urllib.parse.quote(sheet_name)
DATASET_URL_1 = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"

# File 2: Public CSV from Google Drive
file_id_2 = "1Fswh6Eq_wrsf5FbpaaUve9K0KOZ6q3zg"
DATASET_URL_2 = f"https://drive.google.com/uc?id={file_id_2}"

# File 3: GeoJSON file from Google Drive (used for mapping only)
file_id_3 = "1gnux_uKipCE4f-hiThO7c_WHF8kx8nh8"
GEOJSON_URL = f"https://drive.google.com/uc?id={file_id_3}"


# Load the Google Sheet into a DataFrame
try:
    df = pd.read_csv(DATASET_URL_1)
    st.success("Dataset loaded successfully from Google Sheets.")
except Exception as e:
    st.error(f"Error loading dataset: {e}")
    df = pd.DataFrame()  # fallback to empty DataFrame
# Function to create database connection
def create_connection(db_path):
    return sqlite3.connect(db_path)

# Function to create user database
def setup_user_database():
    conn = create_connection(USER_DB)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT
                      )''')
    conn.commit()
    conn.close()

# Function to create vaccination database
def setup_vaccination_database():
    conn = create_connection(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS vaccination_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        STATE TEXT,
                        CITY TEXT,
                        AGE_GROUP TEXT,
                        GENDER TEXT,
                        ETHNICITY TEXT,
                        VACCINATED BOOLEAN,
                        Year INTEGER,
                        DESCRIPTION TEXT
                      )''')
    conn.commit()
    conn.close()

# Function to check if data exists in the table
def is_data_present():
    conn = create_connection(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vaccination_data")
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

# Function to load dataset into the database (only if empty)
def load_data_into_db():
    if not is_data_present():
        try:
            df = pd.read_csv(DATASET_URL)  # Load directly from Google Sheets
            conn = create_connection(DB_FILE)
            df.to_sql("vaccination_data", conn, if_exists="replace", index=False)
            conn.close()
            print("✅ Data loaded into the database successfully!")
        except Exception as e:
            print(f"❌ Error loading dataset: {e}")


# Initialize databases
setup_user_database()
setup_vaccination_database()
load_data_into_db()

