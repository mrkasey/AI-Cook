"""
Streamlit entry point for the AI Meal Assistant.
API key is held in session state only — never written to disk.
"""
from __future__ import annotations
import streamlit as st

from models import Profile, Recipe, DayMealPlan
from agent import get_meal_plan, get_recipe_for_dish, get_pantry_recipe, init_client
from render import render_recipe_card, render_recipe_actions, render_meal_plan_card

st.set_page_config(page_title="AI Meal Assistant", page_icon="🍽️", layout="wide")


# ── Session state defaults ────────────────────────────────────────────────────

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""
if "profile" not in st.session_state:
    st.session_state["profile"] = Profile(
        weight_kg=70.0, height_cm=170.0, goal="maintain",
        diet="vegetarian", servings=2,
    )
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "flow" not in st.session_state:
    st.session_state["flow"] = None


# ── Cached wrappers ───────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _cached_meal_plan(profile_json: str, cuisines_key: str) -> DayMealPlan:
    cuisines = cuisines_key.split("||")
    return get_meal_plan(Profile.model_validate_json(profile_json), cuisines)


@st.cache_data(show_spinner=False)
def _cached_recipe_for_dish(dish: str, profile_json: str) -> Recipe:
    return get_recipe_for_dish(dish, Profile.model_validate_json(profile_json))


@st.cache_data(show_spinner=False)
def _cached_pantry_recipe(items_key: str, profile_json: str) -> tuple:
    items = items_key.split("||")
    return get_pantry_recipe(items, Profile.model_validate_json(profile_json))


# ── Handle pending dish click (from meal plan buttons) ────────────────────────

if st.session_state.get("pending_dish"):
    dish = st.session_state.pop("pending_dish")
    profile_json = st.session_state["profile"].model_dump_json()
    with st.spinner(f"Getting recipe for {dish}…"):
        recipe = _cached_recipe_for_dish(dish, profile_json)
    st.session_state["messages"].append({"role": "user", "content": f"Full recipe for {dish}"})
    st.session_state["messages"].append({"role": "assistant", "type": "recipe", "content": recipe})
    st.session_state["flow"] = "post_recipe"
    st.rerun()


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Your Profile")

    # ── API key ───────────────────────────────────────────────────────────────
    st.markdown("**OpenAI API Key**")
    api_key_input = st.text_input(
        "OpenAI API Key",
        value=st.session_state["api_key"],
        type="password",
        placeholder="sk-proj-...",
        label_visibility="collapsed",
        help="Your key is used only for this session and never stored.",
    )
    if st.session_state["api_key"]:
        st.caption("🔑 Key active for this session")

    st.divider()

    # ── Profile form ──────────────────────────────────────────────────────────
    with st.form("profile_form"):
        p = st.session_state["profile"]
        GOALS = ["lose_weight", "maintain", "gain_muscle"]
        DIETS = ["vegetarian", "vegan", "non-veg", "keto", "paleo", "gluten-free"]

        weight   = st.number_input("Weight (kg)", 30.0, 200.0, float(p.weight_kg), 0.5)
        height   = st.number_input("Height (cm)", 100.0, 250.0, float(p.height_cm), 0.5)
        goal     = st.selectbox("Goal", GOALS, index=GOALS.index(p.goal),
                                format_func=lambda x: x.replace("_", " ").title())
        diet     = st.selectbox("Diet", DIETS, index=DIETS.index(p.diet))
        servings = st.slider("Servings", 1, 6, p.servings)
        saved    = st.form_submit_button("Save Profile ✓", use_container_width=True)

    if saved:
        if not api_key_input.strip():
            st.error("Please enter your OpenAI API key first.")
        else:
            st.session_state["api_key"] = api_key_input.strip()
            st.session_state["profile"] = Profile(
                weight_kg=weight, height_cm=height, goal=goal,
                diet=diet, servings=servings,
            )
            init_client(api_key_input.strip())
            goal_label = goal.replace("_", " ")
            st.session_state["messages"].append({
                "role": "assistant",
                "content": (
                    f"Profile saved! I'll suggest **{diet}** meals "
                    f"to help you **{goal_label}**, {servings} serving(s). "
                    f"What would you like to do?"
                ),
            })
            st.session_state["flow"] = "options"
            st.success("Profile ready!")
            st.rerun()


# ── Main area ─────────────────────────────────────────────────────────────────

st.title("🍽️ AI Meal Assistant")
st.caption("Personalized recipes · Pantry-aware cooking · Macro tracking")

if not st.session_state["api_key"]:
    st.info("👈 Enter your **OpenAI API key** and fill in your profile in the sidebar to get started.")
    st.stop()

# Render chat history
for idx, msg in enumerate(st.session_state["messages"]):
    avatar = "👨‍🍳" if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        msg_type = msg.get("type")
        if msg_type == "recipe":
            render_recipe_card(msg["content"])
            if idx == len(st.session_state["messages"]) - 1:
                render_recipe_actions(msg["content"])
        elif msg_type == "meal_plan":
            render_meal_plan_card(msg["content"], idx)
        else:
            st.markdown(msg["content"])


# ── Active flow UI ────────────────────────────────────────────────────────────

flow = st.session_state.get("flow")

if flow is None:
    st.info("👈 Fill in your profile in the sidebar and hit **Save Profile** to get started.")

elif flow == "post_recipe":
    pass  # action buttons are rendered inside the recipe card above

elif flow == "options":
    st.divider()
    st.markdown("#### What would you like to do?")
    c1, c2, c3 = st.columns(3, gap="large")

    with c1:
        st.markdown("##### 🍜 I have a dish in mind")
        st.caption("Tell me the dish — I'll give you the full recipe, macros & shopping links.")
        if st.button("Choose →", key="opt1", use_container_width=True, type="primary"):
            st.session_state["messages"].append({"role": "user", "content": "I have a dish in mind"})
            st.session_state["messages"].append({"role": "assistant", "content": "Great! What dish are you thinking of?"})
            st.session_state["flow"] = "dish_input"
            st.rerun()

    with c2:
        st.markdown("##### 🗓️ Surprise me")
        st.caption("Not sure what to eat? I'll plan your full day — click any dish to get its recipe.")
        if st.button("Choose →", key="opt2", use_container_width=True, type="primary"):
            st.session_state["messages"].append({"role": "user", "content": "Surprise me with a meal plan for today"})
            st.session_state["messages"].append({
                "role": "assistant",
                "content": "Which cuisines are you in the mood for? Pick one or more and I'll mix them across your meals:",
            })
            st.session_state["flow"] = "surprise_me"
            st.rerun()

    with c3:
        st.markdown("##### 🧅 Use what I have")
        st.caption("List up to 5 ingredients — I'll suggest extras and find the best recipe.")
        if st.button("Choose →", key="opt3", use_container_width=True, type="primary"):
            st.session_state["messages"].append({"role": "user", "content": "I want to cook with what I have at home"})
            st.session_state["messages"].append({
                "role": "assistant",
                "content": "What do you have at home? Enter up to 5 ingredients below:",
            })
            st.session_state["flow"] = "pantry_input"
            st.rerun()

elif flow == "surprise_me":
    ALL_CUISINES = [
        "Indian", "Mediterranean", "East Asian", "Mexican",
        "Italian", "American", "Middle Eastern", "Japanese",
        "Thai", "Korean", "Lebanese", "Greek",
    ]
    selected = st.multiselect(
        "Pick your cuisines for today:",
        ALL_CUISINES,
        default=["Indian", "Mediterranean"],
        key="surprise_cuisines",
    )
    if st.button("Generate my meal plan →", type="primary", disabled=not selected):
        cuisines_key = "||".join(sorted(selected))
        profile_json = st.session_state["profile"].model_dump_json()
        st.session_state["messages"].append({"role": "user", "content": f"Cuisines: {', '.join(selected)}"})
        with st.spinner("Planning your day…"):
            plan = _cached_meal_plan(profile_json, cuisines_key)
        st.session_state["messages"].append({"role": "assistant", "type": "meal_plan", "content": plan})
        st.session_state["flow"] = "options"
        st.rerun()

elif flow == "dish_input":
    if dish_name := st.chat_input("Enter a dish name…"):
        st.session_state["messages"].append({"role": "user", "content": dish_name})
        profile_json = st.session_state["profile"].model_dump_json()
        with st.spinner(f"Getting recipe for {dish_name}…"):
            recipe = _cached_recipe_for_dish(dish_name, profile_json)
        st.session_state["messages"].append({"role": "assistant", "type": "recipe", "content": recipe})
        st.session_state["flow"] = "options"
        st.rerun()

elif flow == "pantry_input":
    placeholders = ["e.g. onions", "e.g. tomatoes", "e.g. paneer", "e.g. rice", "e.g. eggs"]
    with st.form("pantry_form"):
        st.markdown("**Enter up to 5 ingredients you have at home:**")
        cols = st.columns(5)
        inputs = [
            cols[i].text_input(
                f"Item {i + 1}",
                key=f"pi_{i}",
                label_visibility="collapsed",
                placeholder=placeholders[i],
            )
            for i in range(5)
        ]
        go = st.form_submit_button("Find a recipe →", use_container_width=True, type="primary")

    if go:
        items = [x.strip() for x in inputs if x.strip()]
        if not items:
            st.warning("Please enter at least one ingredient.")
        else:
            items_str = ", ".join(items)
            st.session_state["messages"].append({"role": "user", "content": f"I have: {items_str}"})
            items_key = "||".join(items)
            profile_json = st.session_state["profile"].model_dump_json()
            with st.spinner("Checking your pantry and crafting a recipe…"):
                recipe, ai_additions = _cached_pantry_recipe(items_key, profile_json)
            if ai_additions:
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": (
                        f"I also added **{', '.join(ai_additions)}** "
                        f"to round out the dish — here's what I came up with:"
                    ),
                })
            st.session_state["messages"].append({"role": "assistant", "type": "recipe", "content": recipe})
            st.session_state["flow"] = "options"
            st.rerun()
