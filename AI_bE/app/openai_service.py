import re
import httpx
import json
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
import feedparser

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

WEATHER_API_URL = os.getenv("WEATHER_API_URL")
NEWS_API_TOP_HEADLINES_URL = os.getenv("NEWS_API_TOP_HEADLINES_URL")
NEWS_API_EVERYTHING_URL = os.getenv("NEWS_API_EVERYTHING_URL")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Optional: normalize common locations
LOCATION_MAPPING = {
    "delhi": "New Delhi",
    "mumbai": "Mumbai",
    "chennai": "Chennai",
    "bangalore": "Bangalore",
    "kolkata": "Kolkata",
    "hyderabad": "Hyderabad",
    "india": "India"
}

def normalize_location(location: str) -> str:
    if not location:
        return "India"
    key = location.lower().replace(" ", "").replace("-", "")
    return LOCATION_MAPPING.get(key, location.title())


# ----------------------------------------
# Step 1: Ask GPT what to fetch
# ----------------------------------------
async def detect_info_needed(question: str) -> dict:
    """Ask GPT what info (weather/news) is needed, and extract location/topic."""
    system_prompt = (
        "You are an AI assistant. Based on the user question, decide if weather or news is needed.\n"
        "Reply in JSON format like:\n"
        '{"weather": true/false, "news": true/false, "location": "<city>", "topic": "<topic-or-null>"}'
    )

    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
    )

    raw_text = response.choices[0].message.content.strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        print("❌ Failed to parse GPT response:", raw_text)
        return {"weather": False, "news": False, "location": "India", "topic": None}

# ----------------------------------------
# Step 2: Weather API
# ----------------------------------------
async def get_weather(city: str):
    async with httpx.AsyncClient() as http_client:
        res = await http_client.get(
            WEATHER_API_URL,
            params={
                "q": city,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric"
            }
        )
        res.raise_for_status()
        return res.json()

async def get_weather_update(city: str):
    try:
        weather = await get_weather(city)
        desc = weather['weather'][0]['description']
        temp = weather['main']['temp']
        hum = weather['main']['humidity']
        wind = weather['wind']['speed']
        return f"The weather in {city} is {desc}, {temp}°C, humidity {hum}%, wind {wind} m/s."
    except Exception as e:
        print("Weather error:", e)
        return f"Could not get weather for {city}."

# ----------------------------------------
# Step 3: News API
# ----------------------------------------

async def get_news(city: str, topic: str = None):
    try:
        normalized = normalize_location(city)
        query = f"{normalized} {topic}" if topic else normalized
        query = query.replace(" ", "+")
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

        feed = feedparser.parse(rss_url)

        if not feed.entries:
            return f"No news found for {normalized} on topic '{topic}'." if topic else f"No general news found for {normalized}."

        summary = "\n".join([f"- {entry.title}" for entry in feed.entries[:5]])
        return f"Top news in {normalized} ({topic or 'general'}):\n{summary}"
    except Exception as e:
        print("News RSS error:", e)
        return f"Could not retrieve news for {city}."
    
# async def get_news(city: str, topic: str = None):
#     try:
#         normalized = normalize_location(city)
#         async with httpx.AsyncClient() as http_client:
#             if topic:
#                 query = f"{normalized} {topic}"
#                 params = {
#                     "apiKey": NEWS_API_KEY,
#                     "language": "en",
#                     "q": query,
#                     "sortBy": "publishedAt",
#                     "pageSize": 5
#                 }
#                 url = NEWS_API_EVERYTHING_URL
#             else:
#                 params = {
#                     "apiKey": NEWS_API_KEY,
#                     "language": "en",
#                     "pageSize": 5
#                 }
#                 if normalized.lower() != "india":
#                     params["q"] = normalized
#                 else:
#                     params["country"] = "in"
#                 url = NEWS_API_TOP_HEADLINES_URL

#             res = await http_client.get(url, params=params)
#             res.raise_for_status()
#             articles = res.json().get("articles", [])
#             if articles:
#                 summary = "\n".join([f"- {a['title']}" for a in articles])
#                 return f"Top news in {normalized} ({topic or 'general'}):\n{summary}"
#             else:
#                 return f"No {topic or 'general'} news found for {normalized}."
#     except Exception as e:
#         print("News error:", e)
#         return f"Could not retrieve news for {city}."

# ----------------------------------------
# Step 4: OpenAI Response Generator
# ----------------------------------------
async def generate_openai_response_stream(user_question: str):
    try:
        info = await detect_info_needed(user_question)

        city = normalize_location(info.get("location", "India"))
        topic = info.get("topic", None)

        info_parts = []

        if info.get("weather"):
            info_parts.append(await get_weather_update(city))
        if info.get("news"):
            info_parts.append(await get_news(city, topic))

        context_info = "\n\n".join(info_parts) or "No relevant data found."

        stream = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that gives local weather, news, or answers general questions concisely."
                },
                {
                    "role": "user",
                    "content": f"Question: {user_question}\n\nInfo:\n{context_info}"
                }
            ],
            stream=True
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        print("OpenAI Stream error:", e)
        yield "Sorry, something went wrong."

