from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field




class Profile(BaseModel):
    weight_kg: float = Field(..., description="Body weight in kilograms")
    height_cm: float = Field(..., description="Height in centimetres")
    goal: str = Field(..., description="Fitness goal: lose_weight | maintain | gain_muscle")
    diet: str = Field(..., description="Dietary preference e.g. vegetarian, vegan, non-veg, keto")
    servings: int = Field(default=2, description="Number of servings to prepare")


class Macros(BaseModel):
    calories: int = Field(..., description="Total calories per serving")
    protein_g: float = Field(..., description="Protein in grams per serving")
    carbs_g: float = Field(..., description="Carbohydrates in grams per serving")
    fats_g: float = Field(..., description="Fats in grams per serving")


class Recipe(BaseModel):
    dish_name: str = Field(..., description="Name of the dish")
    ingredients: List[str] = Field(..., description="List of required ingredients with quantities")
    optional_extras: List[str] = Field(default_factory=list, description="Optional add-ons or garnishes")
    recipe_steps: List[str] = Field(..., description="Ordered cooking instructions")
    macros: Macros = Field(..., description="Nutritional information per serving")
    missing_ingredients: List[str] = Field(
        default_factory=list,
        description="Ingredients from the recipe that were not in the provided pantry",
    )


class DayMealPlan(BaseModel):
    breakfast: str = Field(..., description="Breakfast dish name")
    lunch: str = Field(..., description="Lunch dish name")
    dinner: str = Field(..., description="Dinner dish name")
    snack: str = Field(default="", description="Optional snack or light evening bite")
