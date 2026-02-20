import json
import os
from typing import List, Dict, Any
from flask import Flask, request, jsonify
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('goodfoods.api')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def _load_json(filename):
    path = os.path.join(BASE_DIR, filename)
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded {filename}")
        return data
    except FileNotFoundError:
        logger.error(f"{filename} not found at {path}")
        return []

order_management_table: List[Dict[str, Any]] = _load_json('bookings_list.json')
restaurant_information_table: List[Dict[str, Any]] = _load_json('restaurant_list.json')

app = Flask(__name__)
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "GoodFoods API (Flask)"})

def search_restaurant_information(query: Dict[str, Any]) -> Dict:
    logger.info(f"Search query: {query}")
    query = {k: v for k, v in query.items() if v}
    top_10 = restaurant_information_table[:10]

    if not query:
        return {
            "status": "empty query",
            "message": "Empty query — returning top restaurants.",
            "restaurants": top_10
        }

    matches = []
    for restaurant in restaurant_information_table:
        match_count = 0
        matched_fields = {}

        for key, value in query.items():
            if key == "cuisine":
                cuisines = restaurant.get("cuisine", [])
                hit = (
                    any(value.lower() in c.lower() for c in cuisines)
                    if isinstance(value, str)
                    else any(c in cuisines for c in value)
                )
                if hit:
                    match_count += 1
                    matched_fields[key] = True

            elif key == "location":
                loc = restaurant.get("location", {})
                if (str(value).lower() in loc.get("address", "").lower() or
                        str(value).lower() in loc.get("landmark", "").lower()):
                    match_count += 1
                    matched_fields[key] = True

            elif key == "operating_days":
                days = restaurant.get("operating_days", [])
                if any(str(value).lower() in d.lower() for d in days):
                    match_count += 1
                    matched_fields[key] = True

            elif key == "operating_hours":
                rh = restaurant.get("operating_hours", {})
                ok = True
                if "open" in value and rh.get("open") != value["open"]:
                    ok = False
                if "close" in value and rh.get("close") != value["close"]:
                    ok = False
                if ok:
                    match_count += 1
                    matched_fields[key] = True

            elif key in ("restaurant_max_seating_capacity", "max_booking_party_size"):
                try:
                    if restaurant.get(key, 0) >= int(str(value).strip()):
                        match_count += 1
                        matched_fields[key] = True
                except (ValueError, TypeError):
                    pass

            else:
                if restaurant.get(key) == value:
                    match_count += 1
                    matched_fields[key] = True

        if match_count > 0:
            matches.append({
                "restaurant": restaurant,
                "match_count": match_count,
                "matched_fields": matched_fields
            })

    matches.sort(key=lambda x: x["match_count"], reverse=True)

    if not matches:
        return {
            "status": "no_matches",
            "message": "No matches — here are top options.",
            "restaurants": top_10
        }

    return {
        "status": "matches_found",
        "message": f"Found {len(matches)} restaurant(s) matching your criteria.",
        "restaurants": [
            {**m["restaurant"], "matched_fields": m["matched_fields"], "match_count": m["match_count"]}
            for m in matches
        ]
    }


def detect_placeholder_values(order_info: Dict) -> Dict:
    placeholder_names = [
        "user", "your name", "your full name", "name", "customer", "customer name",
        "placeholder", "john doe", "jane doe", "[name]", "(name)", "guest", "your_name"
    ]
    placeholder_contacts = [
        "contact", "your contact", "phone", "phone number", "contact number",
        "mobile", "user contact", "123456789", "1234567890"
    ]

    has_placeholders = False
    placeholder_fields = []

    name = str(order_info.get("orderer_name", "")).lower().strip()
    if any(p in name for p in placeholder_names):
        has_placeholders = True
        placeholder_fields.append("orderer_name")

    contact = str(order_info.get("orderer_contact", "")).strip()
    if any(p in contact.lower() for p in placeholder_contacts):
        has_placeholders = True
        placeholder_fields.append("orderer_contact")
    elif not contact.isdigit() or len(contact) != 10:
        has_placeholders = True
        placeholder_fields.append("orderer_contact")

    for field in ("reservation_date", "reservation_time"):
        val = str(order_info.get(field, "")).lower()
        if any(w in val for w in ("tomorrow", "tonight", "today", "next")):
            has_placeholders = True
            placeholder_fields.append(field)

    return {"has_placeholders": has_placeholders, "placeholder_fields": placeholder_fields}


def check_capacity(restaurant_id, party_size, date, time_str, debug=False):
    restaurant = next((r for r in restaurant_information_table if r["restaurant_id"] == restaurant_id), None)
    if not restaurant:
        return False

    max_cap = restaurant["restaurant_max_seating_capacity"]
    current = sum(
        o["party_size"] for o in order_management_table
        if o["restaurant_id"] == restaurant_id
        and o["reservation_date"] == date
        and o["reservation_time"] == time_str
    )
    within = (current + party_size) <= max_cap

    if debug:
        return {
            "is_within_capacity": within,
            "restaurant_id": restaurant_id,
            "max_capacity": max_cap,
            "current_total": current,
            "requested_party_size": party_size,
            "available_capacity": max_cap - current
        }
    return within


def make_new_order(order_info: Dict, capacity_debug: bool = False) -> Dict:
    required = ["restaurant_id", "orderer_name", "orderer_contact",
                "party_size", "reservation_date", "reservation_time"]
    missing = [f for f in required if not order_info.get(f)]
    ph = detect_placeholder_values(order_info)

    if missing or ph["placeholder_fields"]:
        return {
            "status": "error",
            "message": "Validation failed",
            "missing_fields": missing,
            "placeholder_fields": ph["placeholder_fields"]
        }

    cap = check_capacity(
        order_info["restaurant_id"], order_info["party_size"],
        order_info["reservation_date"], order_info["reservation_time"],
        debug=capacity_debug
    )

    if isinstance(cap, dict):
        if not cap["is_within_capacity"]:
            return {"status": "error", "message": "Capacity exceeded.", "capacity_details": cap}
    elif not cap:
        return {"status": "error", "message": "Capacity exceeded."}

    order_id = f"ord{len(order_management_table) + 1:03d}"
    new_order = {**order_info, "order_id": order_id, "status": "confirmed"}
    order_management_table.append(new_order)

    bookings_path = os.path.join(BASE_DIR, 'bookings_list.json')
    try:
        with open(bookings_path, 'w') as f:
            json.dump(order_management_table, f, indent=2)
        logger.info(f"Order saved: {order_id}")
    except Exception as e:
        logger.error(f"Failed to save order: {e}")

    return {"status": "success", "message": "Reservation confirmed", "order": new_order}

@app.route("/restaurants/search", methods=["POST"])
def api_search_restaurants():
    body = request.get_json(silent=True) or {}
    result = search_restaurant_information(body)
    return jsonify(result)


@app.route("/reservations", methods=["POST"])
def api_make_reservation():
    body = request.get_json(silent=True) or {}
    capacity_debug = body.pop("capacity_debug", False)
    result = make_new_order(body, capacity_debug=capacity_debug)
    if result["status"] == "error":
        return jsonify(result), 400
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)