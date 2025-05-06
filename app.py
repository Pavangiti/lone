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
import hashlib

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



# ----------------- USER AUTHENTICATION SYSTEM -----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Function to check if a user exists in the database
def user_exists(username):
    conn = create_connection(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

# Function to add a new user to the database
def add_user(username, password):
    conn = create_connection(USER_DB)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False  # Username already exists

# Function to verify login credentials
def authenticate_user(username, password):
    conn = create_connection(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    stored_password = cursor.fetchone()
    conn.close()
    if stored_password and stored_password[0] == hash_password(password):
        return True
    return False

# ----------------- LOGIN & SIGNUP PAGES -----------------
def login_page():
    st.title("🔑 Secure Login")
    username = st.text_input("👤 Username")
    password = st.text_input("🔑 Password", type="password")
    
    if st.button("Login"):
        if authenticate_user(username, password):
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.rerun()
        else:
            st.error("❌ Invalid credentials. Please try again.")

    st.write("Don't have an account?")
    if st.button("Sign Up"):
        st.session_state["signup"] = True
        st.rerun()

def signup_page():
    st.title("📝 Create a New Account")
    new_username = st.text_input("👤 Choose a Username")
    new_password = st.text_input("🔑 Choose a Password", type="password")
    confirm_password = st.text_input("🔑 Confirm Password", type="password")

    if st.button("Sign Up"):
        if new_password != confirm_password:
            st.error("❌ Passwords do not match. Try again.")
        elif user_exists(new_username):
            st.error("❌ Username already exists. Try a different one.")
        else:
            if add_user(new_username, new_password):
                st.success("✅ Account created successfully! You can now log in.")
                st.session_state["signup"] = False
                st.rerun()
            else:
                st.error("❌ Something went wrong. Try again.")

    st.write("Already have an account?")
    if st.button("Go to Login"):
        st.session_state["signup"] = False
        st.rerun()

# ----------------- AUTHENTICATION LOGIC -----------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "signup" not in st.session_state:
    st.session_state["signup"] = False

if not st.session_state["authenticated"]:
    if st.session_state["signup"]:
        signup_page()
    else:
        login_page()
    st.stop()


# ----------------- MAIN DASHBOARD -----------------
st.title("📊 Vaccination Administration and Demand Forecasting ")

# Logout Button
if st.sidebar.button("Logout"):
    st.session_state["authenticated"] = False
    st.rerun()

# ----------------- FETCH DATA FROM DATABASE -----------------
conn = create_connection(DB_FILE)
df = pd.read_sql("SELECT * FROM vaccination_data", conn)
conn.close()

st.write("### 🔍 Raw Data Preview")
st.dataframe(df.head())

# ----------------- ADD FILTERS -----------------
st.sidebar.header("🔍 Filter Data")
state = st.sidebar.selectbox("📍 Select State", df["STATE"].dropna().unique())
city = st.sidebar.selectbox("🏙 Select City", df[df["STATE"] == state]["CITY"].dropna().unique())
vaccine = st.sidebar.multiselect("💉 Select Vaccine Type", df["DESCRIPTION"].dropna().unique())

filtered_df = df[(df["STATE"] == state) & (df["CITY"] == city) & (df["DESCRIPTION"].isin(vaccine))]
st.write(f"## 📊 Data for {city}, {state} ({', '.join(vaccine)})")
st.dataframe(filtered_df)




# ----------------- MAP & SUMMARY SECTION -----------------
from geopy.geocoders import Nominatim
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# ----------------- FUNCTION TO GET COORDINATES -----------------
def get_lat_lon(state, city):
    geolocator = Nominatim(user_agent="streamlit_app")
    location = geolocator.geocode(f"{city}, {state}, USA")
    if location:
        return location.latitude, location.longitude
    return None, None



try:
    # Read the GeoJSON using GeoPandas
    city_gdf = gpd.read_file(GEOJSON_URL)

    # Filter GeoJSON for the selected city
    selected_city_boundary = city_gdf[city_gdf["CITY"].str.lower() == city.lower()]

    if not selected_city_boundary.empty:
        # Use representative point as map center
        city_center = selected_city_boundary.geometry.representative_point().iloc[0].coords[0][::-1]

        # Create Folium map centered on city
        m = folium.Map(location=city_center, zoom_start=11)

        # Add city boundary
        folium.GeoJson(
            selected_city_boundary.geometry,
            style_function=lambda x: {
                "fillOpacity": 0,
                "color": "blue",
                "weight": 3
            }
        ).add_to(m)

        st.write(f"### 🗺 City Outline for {city}")
        st_folium(m, width=800, height=500)
    else:
        st.warning(f"City '{city}' not found in GeoJSON.")
except Exception as e:
    st.error(f"Map rendering failed: {e}")














