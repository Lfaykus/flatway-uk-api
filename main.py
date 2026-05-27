from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

app = FastAPI(title="Flatway UK Property Search")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

HOMEDATA_BASE = "https://api.homedata.co.uk/api"
HOMEDATA_API_KEY = "9WOJeF8g.af6JVlqaKIkFKWX9AIEHoc2lLKYRug1s"

def get_headers():
    return {"Authorization": f"Api-Key {HOMEDATA_API_KEY}"}

def homedata_get(endpoint: str, params: dict = None):
    try:
        r = requests.get(
            f"{HOMEDATA_BASE}{endpoint}",
            headers=get_headers(),
            params=params,
            timeout=10,
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def root():
    return {"status": "Flatway UK property API running"}

@app.get("/autocomplete")
def autocomplete(q: str = Query(..., description="Address search query")):
    if not q or len(q) < 3:
        return {"suggestions": [], "type": "address"}
    data = homedata_get("/address/find/", params={"q": q, "limit": 8})
    if not data or "suggestions" not in data:
        return {"suggestions": [], "type": "address"}
    suggestions = []
    seen = set()
    for item in data["suggestions"]:
        uprn = item.get("uprn")
        label = item.get("address") or item.get("full_address")
        postcode = item.get("postcode", "")
        if not uprn or not label:
            continue
        key = str(uprn)
        if key in seen:
            continue
        seen.add(key)
        suggestions.append({"label": label, "uprn": uprn, "postcode": postcode, "type": "address"})
    return {"suggestions": suggestions[:8], "type": "address"}

@app.get("/property/{uprn}")
def get_property_by_uprn(uprn: int):
    data = homedata_get(f"/properties/{uprn}/")
    if not data:
        raise HTTPException(status_code=503, detail="Homedata API unavailable")
    if "data" in data:
        prop_data = data["data"]
    elif "uprn" in data:
        prop_data = data
    else:
        raise HTTPException(status_code=404, detail="Property not found")
    prop = format_property(prop_data)
    sales = homedata_get(f"/properties/{uprn}/sales/")
    if sales and "results" in sales:
        prop["price_history"] = [{"date": s.get("transaction_date"), "price": s.get("price"), "tenure": s.get("tenure")} for s in sales["results"][:10]]
    else:
        prop["price_history"] = []
    return {"property": prop}

def format_property(data: dict) -> dict:
    return {
        "uprn": data.get("uprn"),
        "full_address": data.get("full_address"),
        "address": data.get("address"),
        "postcode": data.get("postcode"),
        "street_name": data.get("street_name"),
        "town": data.get("town_name"),
        "property_type": data.get("property_type"),
        "bedrooms": data.get("bedrooms"),
        "bathrooms": data.get("bathrooms"),
        "floor_area_sqm": data.get("internal_area_sqm") or data.get("epc_floor_area"),
        "epc_rating": data.get("current_energy_rating"),
        "tenure": data.get("tenure"),
        "council_tax_band": data.get("council_tax_band"),
        "has_garden": data.get("has_garden"),
        "last_sold_date": data.get("last_sold_date"),
        "last_sold_price": data.get("last_sold_price"),
        "coordinates": {"lat": data.get("latitude"), "lon": data.get("longitude")} if data.get("latitude") else None,
    }

@app.get("/search/address")
def search_by_address(q: str = Query(..., description="Full address or postcode")):
    data = homedata_get("/address/find/", params={"q": q, "limit": 20})
    if not data or "suggestions" not in data:
        raise HTTPException(status_code=404, detail="No results found")
    results = [{"uprn": item.get("uprn"), "full_address": item.get("address") or item.get("full_address"), "postcode": item.get("postcode")} for item in data["suggestions"]]
    return {"count": len(results), "properties": results}
