import os
from dotenv import load_dotenv
from google import genai

load_dotenv()  # loads your API key from a .env file

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Hello! Tell me a fun fact about space."
)

print(response.text)
