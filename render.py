"""
Render Recipe and DayMealPlan objects as rich Streamlit cards.
"""
from __future__ import annotations
import urllib.parse
import streamlit as st
from models import Recipe, DayMealPlan
from tools import strip_measurement, fetch_youtube_results


# Cache YouTube lookups so reruns don't refetch
@st.cache_data(show_spinner=False)
def _cached_yt(dish: str) -> list:
    return fetch_youtube_results(dish, n=3)


def _safe(text: str) -> str:
    """Sanitize text for fpdf2 core fonts (Helvetica only supports ASCII widths)."""
    import unicodedata
    text = (
        text
        .replace("•", "-")    # bullet •
        .replace("–", "-")    # en dash –
        .replace("—", "-")    # em dash —
        .replace("‘", "'")    # left single quote '
        .replace("’", "'")    # right single quote '
        .replace("“", '"')    # left double quote "
        .replace("”", '"')    # right double quote "
        .replace("…", "...")  # ellipsis …
        .replace("°", " deg") # degree sign °
        .replace("½", "1/2")  # ½
        .replace("¼", "1/4")  # ¼
        .replace("¾", "3/4")  # ¾
        .replace("é", "e")    # é
        .replace("è", "e")    # è
        .replace("ê", "e")    # ê
        .replace("à", "a")    # à
        .replace("â", "a")    # â
    )
    # Decompose remaining accented chars (e.g. ñ → n + combining tilde)
    # then drop anything still outside ASCII
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", errors="replace").decode("ascii")


def _recipe_to_pdf(recipe: Recipe) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # Always use an explicit width so multi_cell never sees 0 remaining space
    W = pdf.w - pdf.l_margin - pdf.r_margin

    def reset() -> None:
        pdf.set_x(pdf.l_margin)

    def heading(text: str, size: int = 14, style: str = "B") -> None:
        reset()
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(W, size * 0.55, _safe(text))

    def body(text: str, style: str = "") -> None:
        reset()
        pdf.set_font("Helvetica", style, 11)
        pdf.multi_cell(W, 7, _safe(text))

    m = recipe.macros

    # ── Title ─────────────────────────────────────────────────────────────────
    heading(recipe.dish_name, size=22, style="B")
    pdf.ln(3)

    # ── Macro bar ─────────────────────────────────────────────────────────────
    reset()
    pdf.set_font("Helvetica", "", 11)
    pdf.set_fill_color(245, 245, 245)
    pdf.set_draw_color(200, 200, 200)
    macro_line = (
        f"{m.calories} kcal  |  Protein: {m.protein_g:.1f}g  |"
        f"  Carbs: {m.carbs_g:.1f}g  |  Fats: {m.fats_g:.1f}g"
    )
    pdf.multi_cell(W, 10, _safe(macro_line), align="C", fill=True, border=1)
    pdf.ln(6)

    # ── Ingredients ───────────────────────────────────────────────────────────
    heading("Ingredients")
    for ing in recipe.ingredients:
        body(f"  - {ing}")

    if recipe.optional_extras:
        pdf.ln(2)
        body("Optional extras:", style="BI")
        for extra in recipe.optional_extras:
            body(f"  - {extra}", style="I")

    if recipe.missing_ingredients:
        pdf.ln(2)
        pdf.set_text_color(200, 50, 50)
        body("Missing from pantry:", style="B")
        pdf.set_text_color(0, 0, 0)
        for mi in recipe.missing_ingredients:
            body(f"  - {mi}")

    pdf.ln(5)

    # ── Steps ─────────────────────────────────────────────────────────────────
    heading("Recipe Steps")
    for i, step in enumerate(recipe.recipe_steps, 1):
        body(f"{i}. {step}")
        pdf.ln(2)

    return bytes(pdf.output())


def render_recipe_card(recipe: Recipe) -> None:
    """Display the recipe as a styled card with macro columns, steps, and links."""

    st.markdown(f"## {recipe.dish_name}")
    st.divider()

    # ── Macro strip ──────────────────────────────────────────────────────────
    m = recipe.macros
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Calories", f"{m.calories} kcal")
    col2.metric("Protein", f"{m.protein_g:.1f} g")
    col3.metric("Carbs", f"{m.carbs_g:.1f} g")
    col4.metric("Fats", f"{m.fats_g:.1f} g")

    st.divider()

    # ── Two-column layout: ingredients + steps ────────────────────────────────
    left, right = st.columns([1, 1.4], gap="large")

    with left:
        st.markdown("### Ingredients")
        for ing in recipe.ingredients:
            st.markdown(f"- {ing}")

        if recipe.optional_extras:
            st.markdown("**Optional extras**")
            for extra in recipe.optional_extras:
                st.markdown(f"- {extra}")

        if recipe.missing_ingredients:
            st.warning("**Missing from pantry:**")
            for mi in recipe.missing_ingredients:
                st.markdown(f"- {mi}")

    with right:
        # ── YouTube results (above steps, expanded by default) ────────────────
        with st.expander("Watch on YouTube", expanded=True):
            yt_results = _cached_yt(recipe.dish_name)
            for r in yt_results:
                st.markdown(f"- [{r['title']}]({r['url']})")

        with st.expander("Recipe steps", expanded=False):
            for i, step in enumerate(recipe.recipe_steps, 1):
                st.markdown(f"**{i}.** {step}")

    st.divider()

    # ── Shopping links ────────────────────────────────────────────────────────
    shopping_items = recipe.missing_ingredients or recipe.ingredients
    if shopping_items:
        with st.expander("Shop ingredients", expanded=False):
            for item in shopping_items:
                name = strip_measurement(item)
                q = urllib.parse.quote_plus(name)
                zepto = f"https://www.zeptonow.com/search?query={q}"
                instamart = f"https://www.swiggy.com/instamart/search?query={q}"
                blinkit = f"https://blinkit.com/s/?q={q}"
                st.markdown(
                    f"- **{name}** — "
                    f"[Zepto]({zepto}) · "
                    f"[Instamart]({instamart}) · "
                    f"[Blinkit]({blinkit})"
                )


def render_recipe_actions(recipe: Recipe) -> None:
    """Save / New Recipe / Clear Chat buttons shown after the latest recipe."""
    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            label="💾 Save as PDF",
            data=_recipe_to_pdf(recipe),
            file_name=f"{recipe.dish_name.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with c2:
        if st.button("🔄 New Recipe", use_container_width=True, type="primary"):
            st.session_state["flow"] = "options"
            st.rerun()
    with c3:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state["flow"] = "options"
            st.rerun()


def render_meal_plan_card(plan: DayMealPlan, msg_idx: int) -> None:
    """Display a day's meal plan as clickable dish cards."""
    st.markdown("### Your Day's Meal Plan")
    st.caption("Click any dish to get the full recipe, macros & shopping links.")

    meals = [
        ("☀️ Breakfast", plan.breakfast),
        ("🌤️ Lunch", plan.lunch),
        ("🌙 Dinner", plan.dinner),
    ]
    if plan.snack:
        meals.append(("🍎 Snack", plan.snack))

    cols = st.columns(len(meals))
    for col, (label, dish) in zip(cols, meals):
        with col:
            st.markdown(f"**{label}**")
            st.markdown(f"*{dish}*")
            if st.button("Get recipe →", key=f"mplan_{msg_idx}_{label}"):
                st.session_state["pending_dish"] = dish
