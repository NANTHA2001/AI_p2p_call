import asyncio
import json
import os
import re
from dotenv import load_dotenv
from openai import AsyncOpenAI
import httpx
import feedparser
import wikipedia
import aiohttp

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
WEATHER_API_URL = os.getenv("WEATHER_API_URL")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

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

async def get_weather_update(city: str):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                WEATHER_API_URL,
                params={"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"}
            )
            res.raise_for_status()
            data = res.json()
            desc = data['weather'][0]['description']
            temp = data['main']['temp']
            hum = data['main']['humidity']
            wind = data['wind']['speed']
            return f"The weather in {city} is {desc}, {temp} °C, humidity {hum}%, wind {wind} m/s."
    except Exception as e:
        print("Weather error:", e)
        return f"Could not get weather for {city}."

async def get_news(city: str, topic: str = None):
    try:
        query = f"{city} {topic}" if topic else city
        rss_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(rss_url)
        if not feed.entries:
            return f"No news found for {query}."
        return "Top news:\n" + "\n".join([f"- {entry.title}" for entry in feed.entries[:5]])
    except Exception as e:
        print("News error:", e)
        return f"Could not get news for {city}."

async def fetch_augmented_info(query: str):
    async with aiohttp.ClientSession() as session:
        async def fetch_duckduckgo():
            try:
                url = f"https://api.duckduckgo.com/?q={query.replace(' ', '+')}&format=json&no_redirect=1&skip_disambig=1"
                async with session.get(url) as res:
                    data = await res.json()
                    return data.get("AbstractText")
            except:
                return None

        async def fetch_wiki():
            try:
                return wikipedia.summary(query, sentences=2)
            except:
                return None

        async def fetch_google():
            if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
                return None
            try:
                url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CSE_ID}"
                async with session.get(url) as res:
                    data = await res.json()
                    if "items" in data:
                        return data["items"][0]["snippet"]
            except:
                return None

        results = await asyncio.gather(fetch_duckduckgo(), fetch_wiki(), fetch_google())
        return next((r for r in results if r), "No additional info found.")

def quick_detect_info(question: str):
    q = question.lower()
    location = ""
    match = re.search(r'(?:weather|news) in ([a-zA-Z ]+)', q)
    if match:
        location = match.group(1).strip()
    return {
        "weather": "weather" in q,
        "news": "news" in q,
        "location": normalize_location(location),
        "topic": None
    }

async def generate_openai_response_stream(user_question: str):
    info = quick_detect_info(user_question)
    city = info["location"]
    topic = info.get("topic")

    # Start early
    augment_task = asyncio.create_task(fetch_augmented_info(user_question))
    weather_task = asyncio.create_task(get_weather_update(city)) if info["weather"] else None
    news_task = asyncio.create_task(get_news(city, topic)) if info["news"] else None

    yield "Nova here. Let me check that for you...\n"

    # Parallel context
    context_parts = []
    if weather_task:
        context_parts.append(await weather_task)
    if news_task:
        context_parts.append(await news_task)

    context_text = "\n".join(context_parts) or "No contextual info."

    # Call GPT
    stream = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that answers concisely."},
            {"role": "user", "content": f"Q: {user_question}\n\nContext:\n{context_text}"}
        ],
        stream=True
    )

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

    # Post stream tip
    base = await augment_task
    yield f"\n\nBy the way, I also found this:\n{base}"
