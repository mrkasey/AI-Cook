# AI Meal Assistant

A Streamlit chat app powered by GPT-4o-mini that suggests personalized recipes, handles pantry-aware cooking, tracks macros, and provides grocery + YouTube links.

## Setup

```bash
# 1. Clone / navigate to the project
cd ai_projects/meal_assistant

# 2. Copy and fill in your API key
copy .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# 3. Install dependencies (uses the shared venv)
cd ..
pip install -r req.txt

# 4. Run the app
cd meal_assistant
streamlit run app.py
```

The app opens at **http://localhost:8501**.

## Project structure

```
meal_assistant/
├── models.py     # Pydantic models: Profile, Recipe, Macros
├── tools.py      # Tool schemas + deterministic tools (grocery_links, youtube_links)
├── agent.py      # OpenAI agent loop with tool calling
├── render.py     # Streamlit recipe card renderer
├── app.py        # Main Streamlit app
├── .env.example  # API key template
└── README.md
```

## Features

| Feature | Details |
|---|---|
| Profile sidebar | Weight · Height · Goal · Cuisine · Diet · Servings |
| `suggest_meal` | Full recipe tailored to your profile |
| `cook_with_pantry` | Recipe from what you have; flags missing items |
| `get_macros` | Calories · Protein · Carbs · Fats per serving |
| `grocery_links` | Zepto · Instamart · Blinkit search links |
| `youtube_links` | YouTube Shorts recipe search |
| Response caching | `@st.cache_data` — repeat queries are free |

## Example prompts

- `Suggest me a healthy dinner`
- `I have eggs, spinach, and cheese — what can I cook?`
- `What are the macros for chicken tikka masala?`
- `Give me a high-protein breakfast`
