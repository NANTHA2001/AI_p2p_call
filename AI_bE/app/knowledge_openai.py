import asyncio
import aiohttp
import httpx
import json
import os
import re
from dotenv import load_dotenv
from openai import AsyncOpenAI
import feedparser
import wikipedia

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

WEATHER_API_URL = os.getenv("WEATHER_API_URL")
NEWS_API_TOP_HEADLINES_URL = os.getenv("NEWS_API_TOP_HEADLINES_URL")
NEWS_API_EVERYTHING_URL = os.getenv("NEWS_API_EVERYTHING_URL")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

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


async def detect_info_needed(question: str) -> dict:
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


async def get_weather(city: str):
    async with httpx.AsyncClient() as http_client:
        res = await http_client.get(
            WEATHER_API_URL,
            params={"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"}
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


async def fetch_weather(session, query):
    match = re.search(r'weather in ([a-zA-Z\s]+)', query, re.IGNORECASE)
    if not match:
        return None
    city = match.group(1).strip()
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    try:
        async with session.get(url) as response:
            data = await response.json()
            if "main" in data:
                return f"The current weather in {city} is {data['weather'][0]['description']} with a temperature of {data['main']['temp']}°C."
    except:
        pass
    return None


async def fetch_news(session, query):
    url = f"https://gnews.io/api/v4/search?q={query}&token={NEWS_API_KEY}"
    try:
        async with session.get(url) as response:
            data = await response.json()
            if "articles" in data and data["articles"]:
                article = data["articles"][0]
                return f"Latest news: {article['title']} - {article['description']} ({article['url']})"
    except:
        pass
    return None


async def fetch_wikipedia_summary(query):
    try:
        return wikipedia.summary(query, sentences=2)
    except:
        return None


async def fetch_duckduckgo(session, query):
    url = f"https://api.duckduckgo.com/?q={query.replace(' ', '+')}&format=json&no_redirect=1&skip_disambig=1"
    try:
        async with session.get(url) as response:
            data = await response.json()
            if data.get("AbstractText"):
                return data["AbstractText"]
    except:
        pass
    return None


async def fetch_google_cse(session, query):
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return None
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CSE_ID}"
    try:
        async with session.get(url) as response:
            data = await response.json()
            if "items" in data and data["items"]:
                return data["items"][0]["snippet"]
    except:
        pass
    return None


async def fetch_augmented_answer(query: str) -> str:
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            fetch_weather(session, query),
            fetch_news(session, query),
            fetch_duckduckgo(session, query),
            fetch_wikipedia_summary(query),
            fetch_google_cse(session, query)
        )

        for result in results:
            if result:
                return result

        return "Sorry, I couldn’t find any relevant information."


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

        base_response = await fetch_augmented_answer(user_question)
        context_info += f"\n\nAdditional Info:\n{base_response}"

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