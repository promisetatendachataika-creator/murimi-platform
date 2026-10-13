"""
The options people can pick when they sign up.

These lists must match the ones in web/site/index.html (the ROLES object),
because the server checks every answer against them.
"""

PROVINCES = [
    "Harare", "Bulawayo", "Manicaland", "Mashonaland Central", "Mashonaland East",
    "Mashonaland West", "Masvingo", "Matabeleland North", "Matabeleland South", "Midlands",
]
CROPS = ["Maize", "Tobacco", "Tomatoes", "Potatoes", "Sugar beans", "Citrus", "Cotton", "Avocados", "Other"]

ROLE_FARMER = "farmer"
ROLE_LANDOWNER = "landowner"
ROLE_INVESTOR = "investor"
ROLE_DRIVER = "driver"
ROLE_CHOICES = [
    (ROLE_FARMER, "Farmer"),
    (ROLE_LANDOWNER, "Landowner"),
    (ROLE_INVESTOR, "Diaspora & investor"),
    (ROLE_DRIVER, "Driver & transporter"),
]

# Field spec: (kind, options_or_maxlen, required)
#   kind = "choice" | "multi" | "text" | "number" | "int"
# "province", "area" and "size" are stored in their own columns so staff can
# filter by them in the admin. Everything else goes into Profile.details.
ROLE_FIELDS = {
    ROLE_FARMER: {
        "province": ("choice", PROVINCES, True),
        "area": ("text", 80, True),
        "size": ("number", None, True),
        "crops": ("multi", CROPS, True),
        "needs": ("multi", ["Funding for inputs", "Buyers for my harvest", "Record keeping", "Transport"], True),
    },
    ROLE_LANDOWNER: {
        "province": ("choice", PROVINCES, True),
        "area": ("text", 80, True),
        "size": ("number", None, True),
        "water": ("choice", ["Borehole", "River or dam", "Rain only"], True),
        "use": ("choice", ["Idle", "Partly farmed", "Fully farmed"], True),
        "want": ("multi", ["Partner with a farmer", "Find an investor", "Lease it out"], True),
    },
    ROLE_INVESTOR: {
        "country": ("choice", ["United Kingdom", "South Africa", "United States", "Australia", "Canada",
                               "Ireland", "New Zealand", "Botswana", "Zimbabwe", "Other"], True),
        "experience": ("choice", ["None at all", "A little", "I grew up farming"], True),
        "budget": ("choice", ["Under $1,000", "$1,000–5,000", "$5,000–10,000", "Over $10,000"], True),
        "crops": ("multi", [c for c in CROPS if c != "Other"] + ["Not sure yet"], False),
        "involve": ("choice", ["Just send updates", "Monthly calls", "I'd like to visit"], True),
    },
    ROLE_DRIVER: {
        "area": ("text", 80, True),
        "province": ("choice", PROVINCES, True),
        "trucks": ("multi", ["1 t", "3 t", "8 t", "15 t", "30 t"], True),
        "count": ("int", None, True),
        "cold": ("choice", ["Yes", "No"], True),
        "reach": ("choice", ["Local", "Within my province", "Nationwide"], True),
    },
}

COLUMN_FIELDS = ("province", "area", "size")

CHECKLIST_LENGTH = 4  # each role's "Next steps" list has four items

# Example projects and haulage jobs shown in the dashboards (ids only).
SAVEABLE_IDS = {f"p{i}" for i in range(1, 8)} | {f"j{i}" for i in range(1, 6)}
