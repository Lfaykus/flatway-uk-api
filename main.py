from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests

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
    # Call 1 — property details
    prop_data = homedata_get(f"/properties/{uprn}/")
    # Call 2 — address + coordinates
    addr_data = homedata_get(f"/address/retrieve/{uprn}/")

    if not prop_data and not addr_data:
        raise HTTPException(status_code=404, detail="Property not found")

    merged = {}
    if prop_data and "error" not in prop_data:
        merged.update(prop_data)
    if addr_data and "error" not in addr_data:
        merged.update(addr_data)

    # Call 3 — air quality
    air_quality = None
    air_data = homedata_get("/risks/air_quality_today/", params={"uprn": uprn})
    if air_data and "results" in air_data:
        for r in air_data["results"]:
            if "air" in r.get("risk_type", ""):
                air_quality = {"label": r.get("label"), "score": r.get("score")}

    return {"property": {
        "uprn": merged.get("uprn"),
        "full_address": merged.get("full_address"),
        "address_line_1": merged.get("address_line_1"),
        "postcode": merged.get("postcode"),
        "street_name": merged.get("street_name"),
        "building_number": merged.get("building_number"),
        "town": merged.get("town_name") or merged.get("town"),
        "coordinates": {"lat": merged.get("latitude"), "lon": merged.get("longitude")} if merged.get("latitude") else None,
        "property_type": merged.get("property_type"),
        "tenure": merged.get("tenure"),
        "bedrooms": merged.get("bedrooms"),
        "construction_age_band": merged.get("construction_age_band"),
        "floor_area_sqm": merged.get("total_floor_area") or merged.get("epc_floor_area"),
        "windows_type": merged.get("glazing_type") or merged.get("windows_type"),
        "epc_rating": merged.get("epc_rating"),
        "epc_score": merged.get("epc_current_score") or merged.get("current_energy_efficiency"),
        "epc_potential_score": merged.get("epc_potential_score") or merged.get("potential_energy_efficiency"),
        "last_epc_date": merged.get("epc_inspection_date") or merged.get("last_epc_date"),
        "council_tax_band": merged.get("council_tax_band"),
        "predicted_price": merged.get("predicted_price"),
        "average_area_price": merged.get("average_area_price"),
        "last_sold_date": merged.get("last_sold_date"),
        "last_sold_price": merged.get("last_sold_price"),
        "air_quality": air_quality,
    }}

@app.get("/search/address")
def search_by_address(q: str = Query(..., description="Full address or postcode")):
    data = homedata_get("/address/find/", params={"q": q, "limit": 20})
    if not data or "suggestions" not in data:
        raise HTTPException(status_code=404, detail="No results found")
    results = [{"uprn": item.get("uprn"), "full_address": item.get("address") or item.get("full_address"), "postcode": item.get("postcode")} for item in data["suggestions"]]
    return {"count": len(results), "properties": results}
