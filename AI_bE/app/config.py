
# Keywords to detect weather-related intent
WEATHER_KEYWORDS = [
    "weather", "climate", "forecast", "temperature", "rain", "humidity", "wind",
    "cold", "hot", "sunny", "raining", "cloudy", "storm", "heatwave", "monsoon"
]

# Keywords to detect news-related intent
NEWS_KEYWORDS = [
    "news", "breaking news", "headlines", "latest news", "today news",
    "current events", "top stories", "update", "report", "coverage", "alert"
]

# Keywords to identify specific topics in news
TOPIC_KEYWORDS = [
    "politics", "government", "election", "parliament", "bjp", "congress", "dmk", "aiadmk",
    "sports", "cricket", "football", "ipl", "olympics",
    "technology", "tech", "ai", "artificial intelligence", "startup", "gadgets", "internet",
    "health", "covid", "medicine", "mental health", "hospital", "vaccine",
    "business", "stock market", "economy", "startup", "inflation", "trade", "industry",
    "science", "space", "nasa", "isro", "biology", "chemistry", "research",
    "entertainment", "movies", "cinema", "film", "bollywood", "kollywood", "celebrity", "series", "tv show"
]

# Mapping for normalizing common state and city variations
LOCATION_MAPPING = {
    "tamilnadu": '"Tamil Nadu"', "tamil nadu": '"Tamil Nadu"', "tamil-nadu": '"Tamil Nadu"',
    "delhi": "Delhi", "mumbai": "Mumbai", "chennai": "Chennai", "kolkata": "Kolkata",
    "bangalore": "Bengaluru", "bengaluru": "Bengaluru", "kerala": "Kerala",
    "punjab": "Punjab", "uttarpradesh": '"Uttar Pradesh"', "up": '"Uttar Pradesh"',
    "maharashtra": "Maharashtra", "gujarat": "Gujarat", "andhrapradesh": '"Andhra Pradesh"',
    "telangana": "Telangana", "odisha": "Odisha", "bihar": "Bihar", "india": "India"
}

# Ignore these in extracted locations
SKIP_WORDS_IN_LOCATION = ["uh", "the", "a", "in", "at", "on", "from", "to", "of"]
