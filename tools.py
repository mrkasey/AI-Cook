"""
Tool implementations for the meal assistant agent.
Deterministic tools (grocery_links, youtube_links) return URL strings directly.
AI-backed tools (suggest_meal, cook_with_pantry, get_macros) are executed by the agent loop.
"""
from __future__ import annotations
import json
import re
import urllib.parse
from typing import List

from models import Profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MEASUREMENT_RE = re.compile(
    r"^\s*[\d½¼¾⅓⅔⅛⅜⅝⅞\s./,-]+\s*"
    r"(g|kg|ml|l|litre|liter|cup|cups|tbsp|tsp|tablespoon|tablespoons|"
    r"teaspoon|teaspoons|oz|lb|lbs|piece|pieces|clove|cloves|handful|"
    r"pinch|bunch|sprig|sprigs|inch|cm|medium|large|small|"
    r"can|cans|jar|jars|packet|packets|pack|packs|bottle|bottles|"
    r"head|heads|stalk|stalks|slice|slices|sheet|sheets|"
    r"drop|drops|dash|dashes|to taste)s?\s*",
    re.IGNORECASE,
)


def strip_measurement(ingredient: str) -> str:
    """Remove leading quantity+unit and trailing prep notes from an ingredient string."""
    cleaned = _MEASUREMENT_RE.sub("", ingredient).strip()
    # Drop preparation notes after first comma e.g. "drained and rinsed", "crumbled", "diced"
    cleaned = cleaned.split(",")[0].strip()
    return cleaned if cleaned else ingredient


# ---------------------------------------------------------------------------
# YouTube helper
# ---------------------------------------------------------------------------

def fetch_youtube_results(dish: str, n: int = 3) -> List[dict]:
    """Return up to n YouTube results (title + url) for a recipe search.

    Falls back to a plain search URL if the library fails.
    """
    try:
        from youtube_search import YoutubeSearch
        results = YoutubeSearch(f"{dish} recipe", max_results=n).to_dict()
        return [
            {
                "title": r["title"],
                "url": f"https://www.youtube.com{r['url_suffix']}",
            }
            for r in results
        ]
    except Exception:
        q = urllib.parse.quote_plus(f"{dish} recipe")
        return [{"title": f"Search YouTube for '{dish} recipe'",
                 "url": f"https://www.youtube.com/results?search_query={q}"}]


# ---------------------------------------------------------------------------
# Deterministic tools
# ---------------------------------------------------------------------------

def grocery_links(items: List[str]) -> str:
    """Return markdown hyperlinks for each item on Zepto, Instamart, and Blinkit."""
    lines: List[str] = []
    for item in items:
        search_term = strip_measurement(item)
        q = urllib.parse.quote_plus(search_term)
        zepto = f"https://www.zeptonow.com/search?query={q}"
        instamart = f"https://www.swiggy.com/instamart/search?query={q}"
        blinkit = f"https://blinkit.com/s/?q={q}"
        lines.append(
            f"- **{item}** — "
            f"[Zepto]({zepto}) · "
            f"[Instamart]({instamart}) · "
            f"[Blinkit]({blinkit})"
        )
    return "\n".join(lines)


def youtube_links(dish: str) -> str:
    """Return a YouTube Shorts search URL for the dish recipe."""
    q = urllib.parse.quote_plus(f"{dish} recipe")
    url = f"https://www.youtube.com/shorts?search_query={q}"
    return f"[Watch '{dish}' recipe shorts on YouTube]({url})"


# ---------------------------------------------------------------------------
# Tool schemas for OpenAI function calling
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "suggest_meal",
            "description": (
                "Suggest a complete meal recipe tailored to the user's profile "
                "(weight, height, goal, dietary restrictions, servings). "
                "Returns a Recipe JSON object."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "object",
                        "description": "User profile with weight_kg, height_cm, goal, diet, servings",
                        "properties": {
                            "weight_kg": {"type": "number"},
                            "height_cm": {"type": "number"},
                            "goal": {"type": "string"},
                            "diet": {"type": "string"},
                            "servings": {"type": "integer"},
                        },
                        "required": ["weight_kg", "height_cm", "goal", "diet", "servings"],
                    }
                },
                "required": ["profile"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cook_with_pantry",
            "description": (
                "Suggest a recipe that can be made using the provided pantry items. "
                "Highlights any missing ingredients. Returns a Recipe JSON object."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ingredients currently available in the pantry",
                    },
                    "profile": {
                        "type": "object",
                        "description": "User profile with weight_kg, height_cm, goal, diet, servings",
                        "properties": {
                            "weight_kg": {"type": "number"},
                            "height_cm": {"type": "number"},
                            "goal": {"type": "string"},
                            "diet": {"type": "string"},
                            "servings": {"type": "integer"},
                        },
                        "required": ["weight_kg", "height_cm", "goal", "diet", "servings"],
                    },
                },
                "required": ["items", "profile"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_macros",
            "description": "Return accurate nutritional macros (calories, protein, carbs, fats per serving) for a given dish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dish": {
                        "type": "string",
                        "description": "Name of the dish to look up macros for",
                    }
                },
                "required": ["dish"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grocery_links",
            "description": "Return markdown grocery shopping links (Zepto, Instamart, Blinkit) for a list of ingredients.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ingredient names to generate shopping links for",
                    }
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_links",
            "description": "Return a YouTube Shorts search URL for a recipe video of the given dish.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dish": {
                        "type": "string",
                        "description": "Name of the dish to search YouTube Shorts for",
                    }
                },
                "required": ["dish"],
            },
        },
    },
]


def dispatch_deterministic(name: str, args: dict) -> str | None:
    """Execute the deterministic (non-AI) tools locally and return their string output."""
    if name == "grocery_links":
        return grocery_links(args["items"])
    if name == "youtube_links":
        return youtube_links(args["dish"])
    return None  # signal: this tool needs the AI loop to handle it
