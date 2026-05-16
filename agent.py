"""
Agent loop: sends user message to OpenAI with tool schemas, executes tool calls,
feeds results back, and returns a final structured Recipe object.
"""
from __future__ import annotations
import json
from typing import List

from pydantic import BaseModel, Field

from openai import OpenAI

from models import Profile, Recipe, DayMealPlan
from tools import TOOL_SCHEMAS, dispatch_deterministic

client: OpenAI | None = None


def init_client(api_key: str) -> None:
    """Call once with the user-supplied key before any agent function."""
    global client
    client = OpenAI(api_key=api_key)

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are an expert nutritionist and chef assistant.
Your job is to help users plan meals that fit their dietary goals and preferences.

When a user asks for a meal suggestion or recipe:
1. Use the appropriate tool (suggest_meal or cook_with_pantry) to create a recipe.
2. Use grocery_links to provide shopping links for missing or required ingredients.
3. Use youtube_links to provide a recipe video link.
4. Always return a complete, structured Recipe as your final response.

Be concise, practical, and tailor everything to the user's profile."""


def _build_tool_result_message(tool_call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _execute_ai_tool(name: str, args: dict, profile: Profile) -> str:
    """
    For AI-backed tools (suggest_meal, cook_with_pantry, get_macros),
    make a focused inner call to gpt-4o-mini with structured output (Recipe/Macros).
    """
    if name == "suggest_meal":
        inner_messages = [
            {
                "role": "system",
                "content": (
                    "You are a recipe generator. Given a user profile, produce a complete, "
                    "healthy recipe as a JSON object matching the Recipe schema exactly. "
                    "missing_ingredients should be empty for suggest_meal."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Create a {args['profile']['diet']} recipe "
                    f"for someone who wants to {args['profile']['goal']}, "
                    f"weighs {args['profile']['weight_kg']}kg, is {args['profile']['height_cm']}cm tall, "
                    f"for {args['profile']['servings']} serving(s)."
                ),
            },
        ]
        resp = client.beta.chat.completions.parse(
            model=MODEL,
            messages=inner_messages,
            response_format=Recipe,
        )
        return resp.choices[0].message.parsed.model_dump_json()

    if name == "cook_with_pantry":
        pantry_str = ", ".join(args["items"])
        inner_messages = [
            {
                "role": "system",
                "content": (
                    "You are a recipe generator. Given available pantry ingredients and a user profile, "
                    "produce the best possible recipe using those items. "
                    "List any required ingredients NOT in the pantry under missing_ingredients. "
                    "Return a JSON object matching the Recipe schema exactly."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Pantry: {pantry_str}. "
                    f"Profile: {args['profile']['diet']} diet, "
                    f"goal={args['profile']['goal']}, "
                    f"servings={args['profile']['servings']}."
                ),
            },
        ]
        resp = client.beta.chat.completions.parse(
            model=MODEL,
            messages=inner_messages,
            response_format=Recipe,
        )
        return resp.choices[0].message.parsed.model_dump_json()

    if name == "get_macros":
        from models import Macros
        inner_messages = [
            {
                "role": "system",
                "content": "Return accurate nutritional macros per serving for the requested dish as JSON matching the Macros schema.",
            },
            {"role": "user", "content": f"What are the macros for: {args['dish']}?"},
        ]
        resp = client.beta.chat.completions.parse(
            model=MODEL,
            messages=inner_messages,
            response_format=Macros,
        )
        return resp.choices[0].message.parsed.model_dump_json()

    return json.dumps({"error": f"Unknown AI tool: {name}"})


def run_agent(user_message: str, profile: Profile) -> Recipe:
    """
    Main agent loop.
    - Sends the user message + profile context to gpt-4o-mini.
    - Handles tool calls iteratively until the model returns a final Recipe.
    """
    profile_ctx = (
        f"User profile — weight: {profile.weight_kg}kg, height: {profile.height_cm}cm, "
        f"goal: {profile.goal}, diet: {profile.diet}, servings: {profile.servings}."
    )

    messages: List[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{profile_ctx}\n\n{user_message}"},
    ]

    # Agentic loop — max 6 iterations to avoid runaway calls
    for _ in range(6):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_unset=False))

        # No tool calls → model gave a final text answer; extract Recipe from it
        if not msg.tool_calls:
            # Ask the model to format its answer as a Recipe
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Based on everything above, output the final recipe as a "
                        "structured JSON object matching the Recipe schema. "
                        "Include grocery and YouTube links in optional_extras."
                    ),
                }
            )
            final = client.beta.chat.completions.parse(
                model=MODEL,
                messages=messages,
                response_format=Recipe,
            )
            return final.choices[0].message.parsed

        # Process each tool call
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)

            # Try deterministic tools first
            result = dispatch_deterministic(name, args)

            # Fall back to AI-backed execution
            if result is None:
                result = _execute_ai_tool(name, args, profile)

            messages.append(_build_tool_result_message(tc.id, result))

    # Fallback: ask for a Recipe directly if loop exhausted
    final = client.beta.chat.completions.parse(
        model=MODEL,
        messages=messages,
        response_format=Recipe,
    )
    return final.choices[0].message.parsed


# ---------------------------------------------------------------------------
# Focused single-purpose functions (no tool loop needed)
# ---------------------------------------------------------------------------

def get_meal_plan(profile: Profile, cuisines: List[str]) -> DayMealPlan:
    """Return a day's meal plan with just dish names.

    The model picks one cuisine per meal from the provided list.
    """
    cuisines_str = ", ".join(cuisines)
    resp = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a nutritionist. Suggest a well-balanced day meal plan "
                    "with only dish names (no recipes). For each meal you may choose "
                    "a DIFFERENT cuisine, but it must come from the provided list. "
                    "Tailor to the user's dietary preference and fitness goal."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Plan breakfast, lunch, dinner, and a snack. "
                    f"Choose cuisines from: [{cuisines_str}] — one per meal, can vary. "
                    f"Diet: {profile.diet}, goal={profile.goal}, "
                    f"weight={profile.weight_kg}kg, height={profile.height_cm}cm."
                ),
            },
        ],
        response_format=DayMealPlan,
    )
    return resp.choices[0].message.parsed


def get_recipe_for_dish(dish_name: str, profile: Profile) -> Recipe:
    """Return a full Recipe for a specific named dish, adapted to the user's profile."""
    resp = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a recipe generator. Return a complete Recipe JSON "
                    "for the requested dish, adapted to the user's dietary preference and goal. "
                    "missing_ingredients should be empty."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Full recipe for '{dish_name}', {profile.servings} serving(s). "
                    f"Profile: {profile.diet} diet, goal={profile.goal}, "
                    f"weight={profile.weight_kg}kg."
                ),
            },
        ],
        response_format=Recipe,
    )
    return resp.choices[0].message.parsed


class _IngredientSuggestions(BaseModel):
    suggestions: List[str] = Field(
        ..., description="3-5 complementary ingredients that pair well with the pantry items"
    )


def get_pantry_recipe(user_items: List[str], profile: Profile) -> tuple:
    """
    1. Ask the AI to suggest 3-5 complementary ingredients to add.
    2. Combine with user's items and generate a full Recipe.
    Returns (Recipe, ai_added_ingredients).
    """
    pantry_str = ", ".join(user_items)

    # Step 1 — AI suggests additions
    sugg_resp = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a chef. Given some pantry items, suggest 3-5 common, "
                    "accessible complementary ingredients (spices, staples, etc.) "
                    "that would help make a great dish. Keep suggestions realistic."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Pantry: {pantry_str}. "
                    f"Diet: {profile.diet}. "
                    "What 3-5 ingredients would complement these well?"
                ),
            },
        ],
        response_format=_IngredientSuggestions,
    )
    ai_additions = sugg_resp.choices[0].message.parsed.suggestions

    # Step 2 — Generate recipe with the full combined ingredient list
    all_items = user_items + ai_additions
    recipe_resp = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a recipe generator. Create the best possible recipe "
                    "using the provided ingredients. Any ingredient the recipe needs "
                    "that is NOT in the provided list must appear in missing_ingredients."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Available ingredients: {', '.join(all_items)}. "
                    f"Profile: {profile.diet} diet, "
                    f"goal={profile.goal}, servings={profile.servings}."
                ),
            },
        ],
        response_format=Recipe,
    )
    return recipe_resp.choices[0].message.parsed, ai_additions
