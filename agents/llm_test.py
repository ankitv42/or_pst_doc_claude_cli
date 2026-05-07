"""
Raw grok API call — no frameworks.
Run this first before touching LangChain.
Purpose: understand what LangChain is actually wrapping.
"""

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq()

response = client.chat.completions.create(
    model = "llama-3.1-8b-instant",
    messages = [
        {
            "role": "system",
            "content":  "You are an inventory analyst for a UAE retail chain."
        },
        {
            "role": "user",
            "content": "SKU00090 has 3 units left in STR0077 and sells 5 units per day. What is the urgency level?"
        }
    ],
    temperature=0,
    max_tokens=200,
)

print("=== RESPONSE ===")
print(response.choices[0].message.content)

print("\n=== TOKEN USAGE ===")
print(f"Input tokens  : {response.usage.prompt_tokens}")
print(f"Output tokens : {response.usage.completion_tokens}")
print(f"Total tokens  : {response.usage.total_tokens}")


'''
The messages array — this is how every LLM conversation works. 
system sets the persona. user is your question. 
assistant would be the previous answer if you were building a multi-turn chat. 
LangChain wraps this array but it always boils down to this.


The temperature=0 — zero means the model always gives the same answer. Higher means more creative and variable. 
For agents making inventory decisions you want 0 or close to 0.

'''