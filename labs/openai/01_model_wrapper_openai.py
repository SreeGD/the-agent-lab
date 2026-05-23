from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# Requires OPENAI_API_KEY in .env
model = ChatOpenAI(model="gpt-4o")

response = model.invoke("Explain LangChain in 2 sentences.")
print(response.content)
