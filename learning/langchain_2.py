from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from dotenv import load_dotenv
load_dotenv()

import os

llm = ChatGroq(model=os.getenv('LLM_MODEL'), temperature=0.7, api_key=os.getenv('Groq_API_KEY'))

prompt = ChatPromptTemplate.from_messages([
    ('system', 'You are a helpful assistant having knowledge of {domain}.'),
    ('human', 'What is the {topic}?'),
])

chain = prompt | llm

response = chain.invoke(
    {
    'domain': 'history', 
    'topic': 'capital of France'
    })

# Langchain each componet is runnable(it accepts a single input and produces a single output), so you can 
# create a pipeline of components to process the input and produce the output.

print("=" * 100)

print(response.content)

print("=" * 100)

#====================================================================================================

# If we do not want to leverage the chaining capabilities of langchain, we can also just format the prompt 
# and pass it to the llm directly.

message = prompt.format_messages(
    domain='history', 
    topic='capital of France')

response = llm.invoke(message)

print("=" * 100)
print(response.content)
print("=" * 100)

#====================================================================================================

# One of the feature of runnable component is that we can pass the input to the component and it
# will return the output. This is useful when we want to test the component or when we want to use the 
# component.

llm_component = ChatGroq(model=os.getenv('LLM_MODEL'), temperature=0.7, api_key=os.getenv('Groq_API_KEY'))

response = llm_component.invoke("What is the capital of France?") # we can directly pass the input to the component and it will return the output.
print("=" * 100)
print("llm_component output:", response.content)
print("=" * 100)

# simillarly 
prompt_component = ChatPromptTemplate.from_messages([
    ('system', 'You are a helpful assistant having knowledge of {domain}.'),
    ('human', 'What is the {topic}?'),
])

response = prompt_component.invoke({
    "domain": "history",
    "topic": "capital of France"
})
print("=" * 100)
print("prompt_component output:", response) # the output of the prompt component is a list of messages, which can be passed to the llm component.

# please note the type of response is AIMessage
print("=" * 100)


#===========================Adding Output Parser==============================================================

# Now we add another Runnable.This converts AIMessage → plain string.
from langchain_core.output_parsers import StrOutputParser
parser = StrOutputParser()

# in line no 16 , we have created a chain of prompt and llm. Now we can add another component to the chain which 
# will convert the output of the llm from AIMessage to plain string.


chain = prompt | llm | parser


response = chain.invoke(
    {
    'domain': 'history', 
    'topic': 'capital of France'
    })

print("=" * 100)
print("chain output:", response) # now the output of the chain is a plain string.
print("=" * 100)




