import pandas as pd
import requests
import sqlite3
import streamlit as st
import urllib.parse
from io import StringIO, BytesIO
import hashlib
import folium
import json
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

# ----------------- DATABASE & FILE PATH SETUP -----------------
DB_FILE = "vaccination_data.db"
USER_DB = "users.db"

# ----------------- GOOGLE DRIVE FILE IDS -----------------
sheet_id = "1hJEb7aMjrD-EfAoN9jdhwBK2m9o0U-mh"
sheet_name = "not_vaccinated_analysis (3)"
encoded_sheet_name = urllib.parse.quote(sheet_name)
DATASET_URL_1 = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"

file_id_3 = "1gnux_uKipCE4f-hiThO7c_WHF8kx8nh8"
GEOJSON_URL = f"https://drive.google.com/uc?id={file_id_3}"

# ----------------- DATABASE FUNCTIONS -----------------
def create_connection(db_path):
    return sqlite3.connect(db_path)

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

def is_data_present():
    conn = create_connection(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vaccination_data")
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def load_data_into_db():
    if not is_data_present():
        try:
            df = pd.read_csv(DATASET_URL_1)
            conn = create_connection(DB_FILE)
            df.to_sql("vaccination_data", conn, if_exists="replace", index=False)
            conn.close()
        except Exception as e:
            st.error(f"❌ Error loading dataset into DB: {e}")

# ----------------- USER AUTH -----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def user_exists(username):
    conn = create_connection(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(username, password):
    conn = create_connection(USER_DB)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def authenticate_user(username, password):
    conn = create_connection(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    stored_password = cursor.fetchone()
    conn.close()
    return stored_password and stored_password[0] == hash_password(password)

# ----------------- LOGIN / SIGNUP -----------------
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
            st.error("❌ Invalid credentials.")
    if st.button("Sign Up"):
        st.session_state["signup"] = True
        st.rerun()

def signup_page():
    st.title("📝 Create Account")
    new_username = st.text_input("👤 New Username")
    new_password = st.text_input("🔑 Password", type="password")
    confirm_password = st.text_input("🔑 Confirm Password", type="password")
    if st.button("Register"):
        if new_password != confirm_password:
            st.error("❌ Passwords don't match.")
        elif user_exists(new_username):
            st.error("❌ Username already exists.")
        else:
            if add_user(new_username, new_password):
                st.success("✅ Account created!")
                st.session_state["signup"] = False
                st.rerun()
            else:
                st.error("❌ Registration failed.")
    if st.button("Go to Login"):
        st.session_state["signup"] = False
        st.rerun()

# ----------------- APP STARTUP -----------------
setup_user_database()
setup_vaccination_database()
load_data_into_db()

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

# ----------------- DASHBOARD -----------------
st.title("📊 Vaccination Dashboard")
if st.sidebar.button("Logout"):
    st.session_state["authenticated"] = False
    st.rerun()

# Load data from DB
conn = create_connection(DB_FILE)
df = pd.read_sql("SELECT * FROM vaccination_data", conn)
conn.close()

st.write("### 🔍 Raw Data Preview")
st.dataframe(df.head())

# Filters
st.sidebar.header("🔍 Filter Data")
state = st.sidebar.selectbox("📍 Select State", df["STATE"].dropna().unique())
city = st.sidebar.selectbox("🏙 Select City", df[df["STATE"] == state]["CITY"].dropna().unique())
vaccine = st.sidebar.multiselect("💉 Select Vaccine Type", df["DESCRIPTION"].dropna().unique())

# Filtered data
if vaccine:
    filtered_df = df[(df["STATE"] == state) & (df["CITY"] == city) & (df["DESCRIPTION"].isin(vaccine))]
else:
    filtered_df = df[(df["STATE"] == state) & (df["CITY"] == city)]

st.write(f"## 📈 Data for {city}, {state}")
st.dataframe(filtered_df)

# ----------------- MAP -----------------
try:
    # Load GeoJSON as plain JSON
    response = requests.get(GEOJSON_URL)
    geojson_data = json.loads(response.text)

    # Try to find geometry for selected city
    city_shapes = [feature for feature in geojson_data["features"]
                   if feature["properties"].get("CITY", "").lower() == city.lower()]

    if city_shapes:
        # Get lat/lon using Nominatim
        geolocator = Nominatim(user_agent="streamlit_map")
        location = geolocator.geocode(f"{city}, {state}, USA")
        if location:
            center = [location.latitude, location.longitude]
        else:
            center = [37.0902, -95.7129]  # fallback: center of USA

        m = folium.Map(location=center, zoom_start=11)
        for shape in city_shapes:
            folium.GeoJson(shape, style_function=lambda x: {
                "fillOpacity": 0,
                "color": "blue",
                "weight": 3
            }).add_to(m)

        st.write(f"### 🗺 Map for {city}, {state}")
        st_folium(m, width=800, height=500)
    else:
        st.warning(f"City '{city}' not found in GeoJSON.")

except Exception as e:
    st.error(f"Map rendering failed: {e}")






# ----------------- SHOW TOTAL VACCINATION COUNTS -----------------

# Count total vaccinated and non-vaccinated
total_vaccinated = filtered_df[filtered_df["VACCINATED"] == 1].shape[0]
total_non_vaccinated = filtered_df[filtered_df["VACCINATED"] == 0].shape[0]
total_count = total_vaccinated + total_non_vaccinated

st.write("### 🧮 Total Vaccination Status")

col1, col2, col3 = st.columns(3)
col1.metric(label="✅ Vaccinated", value=total_vaccinated)
col2.metric(label="❌ Non-Vaccinated", value=total_non_vaccinated)
col3.metric(label="📊 Total Records", value=total_count)

#--------- CoMPARISON--------------------------------------------------------------------------------------------------------------------------------------------

st.write("### 📊 Vaccination Trends: Comparison Between Vaccinated & Non-Vaccinated")

# Splitting data into Vaccinated & Non-Vaccinated groups
vaccinated_df = filtered_df[filtered_df["VACCINATED"] == 1]
non_vaccinated_df = filtered_df[filtered_df["VACCINATED"] == 0]

# Creating columns for side-by-side visualization
col1, col2 = st.columns(2)

# Ethnicity Distribution
with col1:
    st.write("### ✅ Vaccinated - Ethnicity Distribution")
    st.plotly_chart(px.pie(vaccinated_df, names="ETHNICITY", title="Vaccinated Ethnicity Distribution"))

with col2:
    st.write("### ❌ Non-Vaccinated - Ethnicity Distribution")
    st.plotly_chart(px.pie(non_vaccinated_df, names="ETHNICITY", title="Non-Vaccinated Ethnicity Distribution"))

# Gender Distribution
col3, col4 = st.columns(2)
with col3:
    st.write("### ✅ Vaccinated - Gender Distribution")
    st.plotly_chart(px.pie(vaccinated_df, names="GENDER", title="Vaccinated Gender Distribution"))

with col4:
    st.write("### ❌ Non-Vaccinated - Gender Distribution")
    st.plotly_chart(px.pie(non_vaccinated_df, names="GENDER", title="Non-Vaccinated Gender Distribution"))

# Age Group Comparison (Bar Chart)
col5, col6 = st.columns(2)
with col5:
    st.write("### ✅ Vaccinated - Age Group")
    st.plotly_chart(px.bar(vaccinated_df, x="AGE_GROUP", title="Vaccination by Age Group"))

with col6:
    st.write("### ❌ Non-Vaccinated - Age Group")
    st.plotly_chart(px.bar(non_vaccinated_df, x="AGE_GROUP", title="Non-Vaccination by Age Group"))

st.write("### 📊 Vaccination Trends (Only Vaccinated)")

# Filter only vaccinated individuals
vaccinated_df = filtered_df[filtered_df["VACCINATED"] == 1]

# ----------------- MAP ETHNICITY TO RACE (If "RACE" Column Doesn't Exist) -----------------
race_mapping = {
    "Hispanic or Latino": "Hispanic",
    "Not Hispanic or Latino": "White",
    "African American": "Black",
    "Asian": "Asian",
    "Native American": "Native American",
    "Pacific Islander": "Pacific Islander",
    "Other": "Other"
}

# If there's no "RACE" column, create one from "ETHNICITY"
if "RACE" not in vaccinated_df.columns:
    vaccinated_df["RACE"] = vaccinated_df["ETHNICITY"].map(race_mapping).fillna("Unknown")
    filtered_df["RACE"] = filtered_df["ETHNICITY"].map(race_mapping).fillna("Unknown")

# ----------------- SHOW RACE-BASED GRAPHS -----------------
st.write("### 📊 Vaccination Trend by Race")

if not vaccinated_df.empty:
    st.plotly_chart(px.bar(vaccinated_df, x="RACE", title="Vaccination by Race", color="RACE"))
else:
    st.warning("No vaccinated data available for the selected filters.")

    
st.write("### 📊 Non-Vaccination Trend by Race")

if not non_vaccinated_df.empty:
    if "RACE" not in non_vaccinated_df.columns:
        non_vaccinated_df["RACE"] = non_vaccinated_df["ETHNICITY"].map(race_mapping).fillna("Unknown")
    st.plotly_chart(px.bar(non_vaccinated_df, x="RACE", title="Non-Vaccination by Race", color="RACE"))
else:
    st.warning("No non-vaccinated data available for the selected filters.")



# ----------------- RACE-BASED BREAKDOWN TABLE -----------------
st.write("### 🧬 Vaccination vs Non-Vaccination Breakdown by Race")

# Ensure 'RACE' column exists
if "RACE" not in vaccinated_df.columns:
    vaccinated_df["RACE"] = vaccinated_df["ETHNICITY"].map(race_mapping).fillna("Unknown")
if "RACE" not in non_vaccinated_df.columns:
    non_vaccinated_df["RACE"] = non_vaccinated_df["ETHNICITY"].map(race_mapping).fillna("Unknown")

# Group by RACE
vaccinated_race_summary = vaccinated_df.groupby("RACE").size().reset_index(name="Vaccinated Count")
non_vaccinated_race_summary = non_vaccinated_df.groupby("RACE").size().reset_index(name="Non-Vaccinated Count")

# Merge summaries
race_summary_table = pd.merge(vaccinated_race_summary, non_vaccinated_race_summary, on="RACE", how="outer").fillna(0)

# Add total row
race_summary_table.loc[len(race_summary_table)] = ["Total", race_summary_table["Vaccinated Count"].sum(), race_summary_table["Non-Vaccinated Count"].sum()]

# Display table
st.dataframe(race_summary_table)



   # ----------------- SHOW SUMMARY TABLE -----------------
# Count total vaccinated and non-vaccinated
total_vaccinated = filtered_df[filtered_df["VACCINATED"] == 1].shape[0]
total_non_vaccinated = filtered_df[filtered_df["VACCINATED"] == 0].shape[0]

# Grouping data for summary
vaccinated_summary = vaccinated_df.groupby(["ETHNICITY", "GENDER", "AGE_GROUP"]).size().reset_index(name="Vaccinated Count")
non_vaccinated_summary = filtered_df[filtered_df["VACCINATED"] == 0].groupby(["ETHNICITY", "GENDER", "AGE_GROUP"]).size().reset_index(name="Non-Vaccinated Count")

# Merging vaccinated and non-vaccinated summaries
summary_table = pd.merge(vaccinated_summary, non_vaccinated_summary, on=["ETHNICITY", "GENDER", "AGE_GROUP"], how="outer").fillna(0)

# Adding total counts
summary_table.loc[len(summary_table)] = ["Total", "Total", "Total", total_vaccinated, total_non_vaccinated]

# Display Table
st.write("### 📊 Vaccination vs Non-Vaccination Breakdown")
st.dataframe(summary_table)

