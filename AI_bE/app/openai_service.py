from openai import AsyncOpenAI
import os

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_openai_response_stream(message: str):
    try:
        stream = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Keep answers very brief (1–2 sentences)."},
                {"role": "user", "content": message},
            ],
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        print("OpenAI Stream error:", e)
        yield "Sorry, something went wrong."
