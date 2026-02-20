# goodfoods-reservation-agent

A conversational AI agent for restaurant table bookings, built with Groq LLM, Flask, and Streamlit. The agent handles the full reservation flow — discovering restaurants, collecting booking details, validating inputs, and confirming reservations — through a natural multi-turn chat interface.

---

## Overview

GoodFoods Reservation Agent is a local agentic AI application that demonstrates how large language models can be wired to real backend APIs using tool calling. The LLM reasons about user intent, decides when to call tools, interprets API results, and guides the user conversationally from inquiry to confirmed booking.

The system has two independently running processes that communicate over HTTP:

- A Flask REST API that manages restaurant data and reservation logic
- A Streamlit chat interface that hosts the Groq-powered conversation agent

---

## Features

- Natural language restaurant search by location, cuisine, party size, and operating hours
- Multi-turn conversation that progressively collects all required booking details
- Tool calling with Groq LLM — the model decides when and how to call each API
- Input validation including placeholder detection, phone number format checks, and capacity verification
- Live agent trace panel showing tool calls and results in real time
- Persistent booking storage via local JSON
- Configurable Groq model via environment variable

---

## Architecture

```
User (Streamlit Chat)
        |
        v
app_goodfoods.py          (Streamlit frontend + conversation loop)
        |
        v
agent/conversation_engine.py    (Groq API calls, tool dispatch, response parsing)
        |
        |--- tool: lookup_dining_options  -->  POST /restaurants/search
        |--- tool: confirm_table_booking  -->  POST /reservations
        |
        v
data/service_api.py       (Flask REST API)
        |
        v
data/restaurant_list.json   (restaurant records)
data/bookings_list.json     (confirmed reservations)
```

The agent follows a single tool-use round per user message:

1. User sends a message
2. Groq LLM receives full conversation history with tools enabled
3. If the LLM decides to call a tool, the tool is dispatched to the Flask API
4. The tool result is appended to history
5. A second Groq call (tools disabled) synthesizes the final reply
6. The reply is displayed in Streamlit

---

## Project Structure

```
goodfoods-reservation-agent/
|
|-- app_goodfoods.py              # Streamlit frontend and conversation orchestration
|-- start.py                      # Launcher script for both Flask and Streamlit
|-- requirements.txt
|-- .env.example
|
|-- agent/
|   |-- conversation_engine.py    # Groq API integration, tool execution, response parsing
|   |-- toolkit.py                # Tool definitions (JSON schema for Groq tool calling)
|   |-- prompt_library.py         # System prompts and few-shot examples
|
|-- data/
    |-- service_api.py            # Flask REST API (restaurant search + reservations)
    |-- restaurant_list.json      # Source data for all restaurant records
    |-- bookings_list.json        # Persisted confirmed reservations
```

---

## Requirements

- Python 3.10 or higher
- A Groq API key (free tier available at https://console.groq.com)

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/your-username/goodfoods-reservation-agent.git
cd goodfoods-reservation-agent
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

```bash
cp .env.example .env
```

Open `.env` and add your Groq API key:

```
GROQ_API_KEY=your_groq_api_key_here
```

Optionally override the default model:

```
GROQ_MODEL=llama-3.3-70b-versatile
```

---

## Running the Application

```bash
python start.py
```

This will:

1. Validate your environment variables
2. Start the Flask API server on `http://localhost:8000`
3. Wait until the API is confirmed running
4. Launch the Streamlit UI on `http://localhost:8501`

Open your browser at `http://localhost:8501` to start using the agent.

To stop the application press `Ctrl+C`.

---

## API Reference

The Flask backend exposes two endpoints.

### POST /restaurants/search

Search for restaurants by any combination of criteria.

Request body (all fields optional):

```json
{
  "location": "MG Road",
  "cuisine": "Italian",
  "max_booking_party_size": 4,
  "operating_days": "Saturday"
}
```

Response:

```json
{
  "status": "matches_found",
  "message": "Found 2 restaurants matching your criteria.",
  "restaurants": [
    {
      "restaurant_id": "r001",
      "name": "GoodFoods MG Road",
      "cuisine": ["Italian", "Mediterranean"],
      "location": {
        "address": "123 MG Road, Bangalore",
        "landmark": "Near Cubbon Park"
      },
      "operating_hours": { "open": "11:00", "close": "23:00" },
      "max_booking_party_size": 8,
      "phone": "080-12345678"
    }
  ]
}
```

### POST /reservations

Create a confirmed reservation. All fields are required.

Request body:

```json
{
  "restaurant_id": "r001",
  "orderer_name": "Rahul Sharma",
  "orderer_contact": "9876543210",
  "party_size": 4,
  "reservation_date": "2026-02-22",
  "reservation_time": "19:00"
}
```

Success response:

```json
{
  "status": "success",
  "message": "Reservation confirmed",
  "order": {
    "restaurant_id": "r001",
    "orderer_name": "Rahul Sharma",
    "orderer_contact": "9876543210",
    "party_size": 4,
    "reservation_date": "2026-02-22",
    "reservation_time": "19:00",
    "order_id": "ord001",
    "status": "confirmed"
  }
}
```

Error response (HTTP 400):

```json
{
  "status": "error",
  "message": "Capacity exceeded.",
  "capacity_details": {
    "max_capacity": 50,
    "current_total": 48,
    "requested_party_size": 4,
    "available_capacity": 2
  }
}
```

---

## Supported Groq Models

Set `GROQ_MODEL` in your `.env` file to switch models.

| Model | Description |
|---|---|
| `llama-3.3-70b-versatile` | Default. Best quality and most reliable tool calling |
| `llama-3.1-8b-instant` | Faster responses, lower cost, suitable for simple queries |
| `mixtral-8x7b-32768` | Long context window, good tool use |

---

## Example Conversation

```
User       : I am looking for Italian food near MG Road for 4 people this Saturday at 7pm

Agent      : I found GoodFoods MG Road which serves Italian and Mediterranean cuisine,
             located near Cubbon Park. It is open until 11 PM on Saturdays and can
             accommodate your party of 4. To confirm the reservation I will need your
             full name and contact number.

User       : Rahul Sharma, 9876543210

Agent      : Your reservation is confirmed. Here are the details:
               Restaurant  : GoodFoods MG Road
               Date        : Saturday, 22nd February 2026
               Time        : 7:00 PM
               Party Size  : 4 people
               Booking ID  : ord001
             You can reach the restaurant at 080-12345678.
```

---

## Validation Rules

The following checks are applied before a reservation is confirmed:

- All six required fields must be present and non-empty
- `orderer_contact` must be exactly 10 digits, numeric only
- `orderer_name` must not be a placeholder value such as "user", "guest", or "your name"
- `reservation_date` must be in `YYYY-MM-DD` format with no relative terms like "tomorrow"
- `party_size` must not exceed the restaurant's `max_booking_party_size`
- Total bookings at the same restaurant, date, and time must not exceed `restaurant_max_seating_capacity`

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | None | Your Groq API key from console.groq.com |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model identifier to use |

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq API (LLaMA 3.3 70B by default) |
| Frontend | Streamlit |
| Backend API | Flask |
| Data validation | Python with custom rule engine |
| Storage | Local JSON files |
| Environment | python-dotenv |

---

## Known Limitations

- The agent handles one tool-call round per user message. Chained tool use within a single turn is not supported.
- Reservation cancellation and modification are not currently implemented.
- Storage uses flat JSON files. For production use, replace with a proper database.
- No authentication or user session management is implemented.

---

## License

MIT License. See LICENSE for details.
