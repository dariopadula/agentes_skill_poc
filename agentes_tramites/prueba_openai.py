from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

resp = client.responses.create(
    model="gpt-5-mini",
    input="Respondé solamente OK"
)

print(resp.output_text)