import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
from supabase import create_client, Client

st.set_page_config(page_title="4-Day Upper/Lower Recomp Tracker", layout="wide")

@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

def load_workouts():
    response = supabase.table("workouts").select("*").order("Date").execute()
    data = response.data if response.data else []
    return pd.DataFrame(data)

def load_nutrition():
    response = supabase.table("nutrition").select("*").order("Date").execute()
    data = response.data if response.data else []
    return pd.DataFrame(data)

def insert_workout(row):
    payload = {
        "Date": str(row["Date"]),
        "Week": int(row["Week"]),
        "Stage": row["Stage"],
        "Day": row["Day"],
        "Bodyweight": float(row["Bodyweight"]),
        "Primary_Exercise": row["Primary Exercise"],
        "Selected_Exercise": row["Selected Exercise"],
        "Category": row["Category"],
        "Sets": float(row["Sets"]),
        "Reps": float(row["Reps"]),
        "Load": float(row["Load"]),
        "RPE": float(row["RPE"]),
        "Notes": row["Notes"]
    }
    supabase.table("workouts").insert(payload).execute()

def insert_nutrition(row):
    payload = {
        "Date": str(row["Date"]),
        "Week": int(row["Week"]),
        "Bodyweight": float(row["Bodyweight"]),
        "Calories": float(row["Calories"]),
        "Protein": float(row["Protein"]),
        "Carbs": float(row["Carbs"]),
        "Fat": float(row["Fat"]),
        "Target_Calories": float(row["Target Calories"]),
        "Target_Protein": float(row["Target Protein"]),
        "Target_Carbs": float(row["Target Carbs"]),
        "Target_Fat": float(row["Target Fat"])
    }
    supabase.table("nutrition").insert(payload).execute()

def load_user_settings():
    """Load user settings from database"""
    response = supabase.table("user_settings").select("*").eq("user_id", "default_user").execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

def update_user_settings(settings):
    """Save user settings to database"""
    supabase.table("user_settings").update(settings).eq("user_id", "default_user").execute()

def get_stage(week):
    if week <= 4:
        return "Foundation", "🟢 Foundation (Weeks 1-4)"
    elif week <= 8:
        return "Build", "🟡 Build (Weeks 5-8)"
    return "Peak", "🔴 Peak (Weeks 9-12)"

def get_stage(week):
    if week <= 4:
        return "Foundation", "🟢 Foundation (Weeks 1-4)"
    elif week <= 8:
        return "Build", "🟡 Build (Weeks 5-8)"
    return "Peak", "🔴 Peak (Weeks 9-12)"

def get_latest_logged_weight(default_weight, workouts_df, nutrition_df):
    latest_weight = float(default_weight)

    if not nutrition_df.empty and "Bodyweight" in nutrition_df.columns:
        nut_df = nutrition_df.copy()
        nut_df["Date"] = pd.to_datetime(nut_df["Date"], errors="coerce")
        nut_df["Bodyweight"] = pd.to_numeric(nut_df["Bodyweight"], errors="coerce")
        nut_df = nut_df.dropna(subset=["Date", "Bodyweight"]).sort_values("Date")
        if not nut_df.empty:
            latest_weight = float(nut_df.iloc[-1]["Bodyweight"])

    if not workouts_df.empty and "Bodyweight" in workouts_df.columns:
        wk_df = workouts_df.copy()
        wk_df["Date"] = pd.to_datetime(wk_df["Date"], errors="coerce")
        wk_df["Bodyweight"] = pd.to_numeric(wk_df["Bodyweight"], errors="coerce")
        wk_df = wk_df.dropna(subset=["Date", "Bodyweight"]).sort_values("Date")
        if not wk_df.empty:
            latest_weight = float(wk_df.iloc[-1]["Bodyweight"])

    return latest_weight

def calculate_macros(bodyweight_lbs, height_inches, age, gender, activity_level, training_experience, goal):
    weight_kg = bodyweight_lbs * 0.453592
    height_cm = height_inches * 2.54

    if gender == "Male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    activity_map = {
        "Sedentary": 1.2,
        "Lightly Active": 1.375,
        "Moderately Active": 1.55,
        "Very Active": 1.725,
        "Extremely Active": 1.9
    }
    tdee = bmr * activity_map[activity_level]

    if training_experience == "Beginner":
        recomp_adj, cut_adj, bulk_adj, protein_g_per_kg = -150, -350, 150, 1.8
    elif training_experience == "Intermediate":
        recomp_adj, cut_adj, bulk_adj, protein_g_per_kg = -200, -450, 200, 2.0
    else:
        recomp_adj, cut_adj, bulk_adj, protein_g_per_kg = -250, -500, 250, 2.2

    if age >= 50:
        protein_g_per_kg = max(protein_g_per_kg, 2.0)

    if goal == "Recomp":
        target_calories = tdee + recomp_adj
    elif goal == "Cut":
        target_calories = tdee + cut_adj
    else:
        target_calories = tdee + bulk_adj

    fat_g_per_kg = 0.7 if goal == "Cut" else 0.9 if goal == "Bulk" else 0.8
    target_protein = weight_kg * protein_g_per_kg
    target_fat = weight_kg * fat_g_per_kg
    target_carbs = max((target_calories - ((target_protein * 4) + (target_fat * 9))) / 4, 0)

    return {
        "bmr": int(round(bmr)),
        "tdee": int(round(tdee)),
        "calories": int(round(target_calories)),
        "protein": int(round(target_protein)),
        "carbs": int(round(target_carbs)),
        "fat": int(round(target_fat))
    }

def calculate_weekly_set_targets(goal, training_experience):
    if training_experience == "Beginner":
        base = {
            "Chest": (8, 12), "Back": (8, 12), "Delts": (6, 10), "Rear Delts": (4, 8),
            "Biceps": (4, 8), "Triceps": (4, 8), "Quads": (8, 12), "Hamstrings": (8, 12),
            "Calves": (4, 8), "Core": (4, 8)
        }
    elif training_experience == "Intermediate":
        base = {
            "Chest": (10, 16), "Back": (10, 16), "Delts": (8, 14), "Rear Delts": (4, 10),
            "Biceps": (5, 10), "Triceps": (5, 10), "Quads": (10, 16), "Hamstrings": (10, 16),
            "Calves": (5, 10), "Core": (4, 8)
        }
    else:
        base = {
            "Chest": (12, 18), "Back": (12, 18), "Delts": (10, 16), "Rear Delts": (6, 12),
            "Biceps": (6, 12), "Triceps": (6, 12), "Quads": (12, 18), "Hamstrings": (12, 18),
            "Calves": (6, 12), "Core": (6, 10)
        }

    if goal == "Cut":
        adjusted = {}
        for k, v in base.items():
            adjusted[k] = (max(v[0] - 2, 4), max(v[1] - 2, 6))
        return adjusted
    return base

def build_program():
    return {
        "Upper 1": {
            "Foundation": {
                "warmup": [
                    "5 min bike or elliptical",
                    "Foam roll T-spine x 45-60 sec",
                    "Quadruped T-spine rotation x 8/side",
                    "Wall slides x 10",
                    "Band pull-aparts x 15",
                    "Band external rotation x 12/side",
                    "Scap push-up x 8",
                    "Dead bug x 8/side",
                    "2-3 ramp-up sets for first press and first row"
                ],
                "primary": [
                    {"exercise": "Machine Chest Press", "category": "Chest", "sets": 3, "reps": 10, "subs": ["DB Floor Press", "Cable Press", "Push-up"]},
                    {"exercise": "Seated Row", "category": "Back", "sets": 3, "reps": 10, "subs": ["Chest-Supported Row", "Cable Row", "Machine Row"]},
                    {"exercise": "Lat Pulldown", "category": "Back", "sets": 3, "reps": 10, "subs": ["High Row", "Assisted Pull-up"]},
                    {"exercise": "Machine Shoulder Press", "category": "Delts", "sets": 2, "reps": 10, "subs": ["Landmine Press", "Incline Press (light)"]},
                    {"exercise": "Face Pull", "category": "Rear Delts", "sets": 2, "reps": 15, "subs": ["Rear Delt Fly", "Band Pull-Apart"]},
                    {"exercise": "DB Curl", "category": "Biceps", "sets": 2, "reps": 12, "subs": ["Hammer Curl", "Cable Curl"]},
                    {"exercise": "Cable Pressdown", "category": "Triceps", "sets": 2, "reps": 12, "subs": ["Overhead Rope Extension", "Bench Dip (assisted)"]}
                ]
            },
            "Build": {
                "warmup": [
                    "5 min bike or elliptical",
                    "Foam roll T-spine x 45-60 sec",
                    "Quadruped T-spine rotation x 10/side",
                    "Wall slides x 10",
                    "Band pull-aparts x 20",
                    "Band external rotation x 15/side",
                    "Scap push-up x 10",
                    "Dead bug x 10/side",
                    "2-3 ramp-up sets for first press and first row"
                ],
                "primary": [
                    {"exercise": "Machine Chest Press", "category": "Chest", "sets": 4, "reps": 8, "subs": ["DB Floor Press", "Cable Press", "Push-up"]},
                    {"exercise": "Seated Row", "category": "Back", "sets": 4, "reps": 8, "subs": ["Chest-Supported Row", "Cable Row", "Machine Row"]},
                    {"exercise": "Lat Pulldown", "category": "Back", "sets": 4, "reps": 8, "subs": ["High Row", "Assisted Pull-up"]},
                    {"exercise": "Machine Shoulder Press", "category": "Delts", "sets": 3, "reps": 8, "subs": ["Landmine Press", "Incline Press (light)"]},
                    {"exercise": "Face Pull", "category": "Rear Delts", "sets": 3, "reps": 12, "subs": ["Rear Delt Fly", "Band Pull-Apart"]},
                    {"exercise": "DB Curl", "category": "Biceps", "sets": 3, "reps": 10, "subs": ["Hammer Curl", "Cable Curl"]},
                    {"exercise": "Cable Pressdown", "category": "Triceps", "sets": 3, "reps": 10, "subs": ["Overhead Rope Extension", "Bench Dip (assisted)"]}
                ]
            },
            "Peak": {
                "warmup": [
                    "5 min bike or elliptical",
                    "Foam roll T-spine x 60 sec",
                    "Quadruped T-spine rotation x 10/side",
                    "Wall slides x 12",
                    "Band pull-aparts x 20",
                    "Band external rotation x 15/side",
                    "Scap push-up x 10",
                    "Dead bug x 10/side",
                    "2-4 ramp-up sets for first press and first row"
                ],
                "primary": [
                    {"exercise": "Machine Chest Press", "category": "Chest", "sets": 4, "reps": 6, "subs": ["DB Floor Press", "Cable Press", "Push-up"]},
                    {"exercise": "Seated Row", "category": "Back", "sets": 4, "reps": 6, "subs": ["Chest-Supported Row", "Cable Row", "Machine Row"]},
                    {"exercise": "Lat Pulldown", "category": "Back", "sets": 4, "reps": 8, "subs": ["High Row", "Assisted Pull-up"]},
                    {"exercise": "Machine Shoulder Press", "category": "Delts", "sets": 3, "reps": 8, "subs": ["Landmine Press", "Incline Press (light)"]},
                    {"exercise": "Face Pull", "category": "Rear Delts", "sets": 3, "reps": 12, "subs": ["Rear Delt Fly", "Band Pull-Apart"]},
                    {"exercise": "DB Curl", "category": "Biceps", "sets": 3, "reps": 10, "subs": ["Hammer Curl", "Cable Curl"]},
                    {"exercise": "Cable Pressdown", "category": "Triceps", "sets": 3, "reps": 10, "subs": ["Overhead Rope Extension", "Bench Dip (assisted)"]}
                ]
            }
        },
        "Lower 1": {
            "Foundation": {
                "warmup": [
                    "5 min bike",
                    "Cat-cow x 8",
                    "Quadruped rock-back x 10",
                    "Glute bridge x 10",
                    "Bird dog x 8/side",
                    "Hip flexor mobilization x 8/side",
                    "Ankle rocks x 10/side",
                    "Bodyweight squat x 10",
                    "2-4 ramp-up sets for first lower-body movement"
                ],
                "primary": [
                    {"exercise": "Leg Press", "category": "Quads", "sets": 4, "reps": 10, "subs": ["Goblet Squat", "Hack Squat Machine", "Box Squat"]},
                    {"exercise": "Hamstring Curl", "category": "Hamstrings", "sets": 3, "reps": 12, "subs": ["Stability Ball Curl", "Glute Bridge"]},
                    {"exercise": "Split Squat", "category": "Quads", "sets": 3, "reps": 10, "subs": ["Step-up", "Reverse Lunge"]},
                    {"exercise": "Calf Raise", "category": "Calves", "sets": 3, "reps": 15, "subs": ["Seated Calf Raise", "Single-Leg Calf Raise"]},
                    {"exercise": "Bird Dog", "category": "Core", "sets": 2, "reps": 10, "subs": ["Dead Bug", "Pallof Press"]}
                ]
            },
            "Build": {
                "warmup": [
                    "5 min bike",
                    "Cat-cow x 8",
                    "Quadruped rock-back x 10",
                    "Glute bridge x 12",
                    "Bird dog x 10/side",
                    "Hip flexor mobilization x 10/side",
                    "Ankle rocks x 10/side",
                    "Bodyweight squat x 10",
                    "2-4 ramp-up sets for first lower-body movement"
                ],
                "primary": [
                    {"exercise": "Leg Press", "category": "Quads", "sets": 4, "reps": 8, "subs": ["Goblet Squat", "Hack Squat Machine", "Box Squat"]},
                    {"exercise": "Hamstring Curl", "category": "Hamstrings", "sets": 4, "reps": 10, "subs": ["Stability Ball Curl", "Glute Bridge"]},
                    {"exercise": "Split Squat", "category": "Quads", "sets": 3, "reps": 8, "subs": ["Step-up", "Reverse Lunge"]},
                    {"exercise": "Calf Raise", "category": "Calves", "sets": 4, "reps": 12, "subs": ["Seated Calf Raise", "Single-Leg Calf Raise"]},
                    {"exercise": "Bird Dog", "category": "Core", "sets": 3, "reps": 10, "subs": ["Dead Bug", "Pallof Press"]}
                ]
            },
            "Peak": {
                "warmup": [
                    "5 min bike",
                    "Cat-cow x 8",
                    "Quadruped rock-back x 10",
                    "Glute bridge x 12",
                    "Bird dog x 10/side",
                    "Hip flexor mobilization x 10/side",
                    "Ankle rocks x 12/side",
                    "Bodyweight squat x 10",
                    "2-4 ramp-up sets for first lower-body movement"
                ],
                "primary": [
                    {"exercise": "Leg Press", "category": "Quads", "sets": 4, "reps": 6, "subs": ["Hack Squat Machine", "Goblet Squat", "Box Squat"]},
                    {"exercise": "Hamstring Curl", "category": "Hamstrings", "sets": 4, "reps": 8, "subs": ["Stability Ball Curl", "Glute Bridge"]},
                    {"exercise": "Split Squat", "category": "Quads", "sets": 4, "reps": 8, "subs": ["Step-up", "Reverse Lunge"]},
                    {"exercise": "Calf Raise", "category": "Calves", "sets": 4, "reps": 15, "subs": ["Seated Calf Raise", "Single-Leg Calf Raise"]},
                    {"exercise": "Bird Dog", "category": "Core", "sets": 3, "reps": 12, "subs": ["Dead Bug", "Pallof Press"]}
                ]
            }
        }
    }

workouts_df = load_workouts()
nutrition_df = load_nutrition()

st.title("4-Day Upper/Lower Recomp Tracker")

st.header("Program Setup")

# Load saved settings
saved_settings = load_user_settings()

# If settings exist in DB, use them; otherwise use defaults
if saved_settings:
    default_weight = saved_settings.get("bodyweight", 168.0)
    default_height = saved_settings.get("height_inches", 70.0)
    default_age = saved_settings.get("age", 52)
    default_gender = saved_settings.get("gender", "Male")
    default_activity = saved_settings.get("activity_level", "Moderately Active")
    default_training = saved_settings.get("training_experience", "Intermediate")
    default_goal = saved_settings.get("goal", "Recomp")
    default_start_date = pd.to_datetime(saved_settings.get("start_date")).date() if saved_settings.get("start_date") else date.today()
else:
    default_weight = 168.0
    default_height = 70.0
    default_age = 52
    default_gender = "Male"
    default_activity = "Moderately Active"
    default_training = "Intermediate"
    default_goal = "Recomp"
    default_start_date = date.today()

c1, c2, c3, c4 = st.columns(4)
with c1:
    current_bodyweight = st.number_input("Current weight (lbs)", 100.0, 400.0, default_weight, 0.5)
with c2:
    height_inches = st.number_input("Height (inches)", 48.0, 84.0, default_height, 0.5)
with c3:
    age = st.number_input("Age", 18, 90, default_age, 1)
with c4:
    gender = st.selectbox("Gender", ["Male", "Female"], index=0 if default_gender == "Male" else 1)

activity_options = {
    "Sedentary — desk job, little formal exercise, low daily movement": "Sedentary",
    "Lightly Active — 1-3 light workouts/week or modest daily walking": "Lightly Active",
    "Moderately Active — 3-5 training sessions/week with decent daily movement": "Moderately Active",
    "Very Active — hard training most days or physically active job": "Very Active",
    "Extremely Active — very high training volume and/or highly physical lifestyle": "Extremely Active"
}

training_options = {
    "Beginner — less than ~6-12 months of consistent lifting, still learning technique": "Beginner",
    "Intermediate — 1-3+ years of fairly consistent lifting, progressing but no longer rapidly": "Intermediate",
    "Advanced — many years of structured lifting, slower gains, needs more precision": "Advanced"
}

# Find the index for saved settings
activity_keys = list(activity_options.keys())
activity_index = next((i for i, k in enumerate(activity_keys) if activity_options[k] == default_activity), 2)

training_keys = list(training_options.keys())
training_index = next((i for i, k in enumerate(training_keys) if training_options[k] == default_training), 1)

c5, c6, c7, c8 = st.columns(4)
with c5:
    start_date = st.date_input("Program start date", value=default_start_date)
with c6:
    current_date = st.date_input("Current date in program", value=date.today())
with c7:
    activity_level_label = st.selectbox("Activity level", activity_keys, index=activity_index)
    activity_level = activity_options[activity_level_label]
with c8:
    training_experience_label = st.selectbox("Training level", training_keys, index=training_index)
    training_experience = training_options[training_experience_label]

goal = st.selectbox("Goal", ["Recomp", "Cut", "Bulk"], index=["Recomp", "Cut", "Bulk"].index(default_goal))

# Save settings button
if st.button("💾 Save Settings", use_container_width=True):
    settings_to_save = {
        "bodyweight": float(current_bodyweight),
        "height_inches": float(height_inches),
        "age": int(age),
        "gender": gender,
        "activity_level": activity_level,
        "training_experience": training_experience,
        "goal": goal,
        "start_date": str(start_date),
        "updated_at": "now()"
    }
    update_user_settings(settings_to_save)
    st.success("✅ Settings saved! They will now appear on all devices.")
    st.rerun()

days_elapsed = max((current_date - start_date).days, 0)
current_week = min((days_elapsed // 7) + 1, 12)
stage_key, stage_label = get_stage(current_week)
program_end = start_date + timedelta(days=83)

# Use current_bodyweight directly for macros (not logged weight)
macros = calculate_macros(
    current_bodyweight, height_inches, age, gender, activity_level, training_experience, goal
)

t1, t2, t3 = st.columns(3)
t1.metric("Current week", current_week)
t2.metric("Current stage", stage_label)
t3.metric("Program end", str(program_end))

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Current bodyweight", f"{current_bodyweight:.1f} lbs")
m2.metric("Calories", f"{macros['calories']}")
m3.metric("Protein", f"{macros['protein']} g")
m4.metric("Carbs", f"{macros['carbs']} g")
m5.metric("Fat", f"{macros['fat']} g")

program = build_program()
selected_day = st.selectbox("Training day", list(program.keys()))
day_plan = program[selected_day][stage_key]

st.header("Daily plan")
left, right = st.columns(2)

with left:
    st.subheader("Warmup")
    for item in day_plan["warmup"]:
        st.write(f"- {item}")

with right:
    st.subheader("Primary exercises")
    for item in day_plan["primary"]:
        st.write(f"- {item['exercise']} — {item['sets']}x{item['reps']} ({item['category']})")

tab1, tab2 = st.tabs(["Workout Log", "Nutrition Log"])

with tab1:
    workout_date = st.date_input("Workout date", value=current_date, key="workout_date")
    bodyweight_today = st.number_input("Bodyweight today (lbs)", 100.0, 400.0, float(current_bodyweight), 0.5, key="bw_today")

    for idx, item in enumerate(day_plan["primary"]):
        st.markdown(f"### {item['exercise']}")
        options = [item["exercise"]] + item["subs"]
        selected_exercise = st.selectbox(f"Movement choice {idx + 1}", options, key=f"select_{idx}_{selected_day}")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sets = st.number_input(f"Sets {idx + 1}", 1, 10, item["sets"], key=f"sets_{idx}_{selected_day}")
        with c2:
            reps = st.number_input(f"Reps {idx + 1}", 1, 50, item["reps"], key=f"reps_{idx}_{selected_day}")
        with c3:
            load = st.number_input(f"Load {idx + 1}", 0.0, 1000.0, 0.0, 5.0, key=f"load_{idx}_{selected_day}")
        with c4:
            rpe = st.number_input(f"RPE {idx + 1}", 1.0, 10.0, 7.0, 0.5, key=f"rpe_{idx}_{selected_day}")

        notes = st.text_input(f"Notes {idx + 1}", key=f"notes_{idx}_{selected_day}")

        if st.button(f"Save {selected_exercise}", key=f"save_{idx}_{selected_day}"):
            row = {
                "Date": workout_date,
                "Week": current_week,
                "Stage": stage_key,
                "Day": selected_day,
                "Bodyweight": bodyweight_today,
                "Primary Exercise": item["exercise"],
                "Selected Exercise": selected_exercise,
                "Category": item["category"],
                "Sets": sets,
                "Reps": reps,
                "Load": load,
                "RPE": rpe,
                "Notes": notes
            }
            insert_workout(row)
            st.success(f"Saved {selected_exercise}")
            st.rerun()

with tab2:
    with st.form("nutrition_form"):
        n1, n2, n3, n4, n5, n6 = st.columns(6)
        with n1:
            nutrition_date = st.date_input("Nutrition date", value=current_date, key="nutrition_date")
        with n2:
            nutrition_bw = st.number_input("Bodyweight", 100.0, 400.0, float(current_bodyweight), 0.5)
        with n3:
            calories_in = st.number_input("Calories eaten", 0, 10000, macros["calories"])
        with n4:
            protein_in = st.number_input("Protein eaten", 0, 500, macros["protein"])
        with n5:
            carbs_in = st.number_input("Carbs eaten", 0, 1000, macros["carbs"])
        with n6:
            fat_in = st.number_input("Fat eaten", 0, 300, macros["fat"])

        submitted_nutrition = st.form_submit_button("Save nutrition")

        if submitted_nutrition:
            row = {
                "Date": nutrition_date,
                "Week": current_week,
                "Bodyweight": nutrition_bw,
                "Calories": calories_in,
                "Protein": protein_in,
                "Carbs": carbs_in,
                "Fat": fat_in,
                "Target Calories": macros["calories"],
                "Target Protein": macros["protein"],
                "Target Carbs": macros["carbs"],
                "Target Fat": macros["fat"]
            }
            insert_nutrition(row)
            st.success("Nutrition saved")
            st.rerun()

st.markdown("---")
st.write(
    f"Current plan: {goal} | {stage_label} | bodyweight driving macros: {current_bodyweight:.1f} lbs | "
    f"targets: {macros['calories']} cal, {macros['protein']} g protein, {macros['carbs']} g carbs, {macros['fat']} g fat."
)
