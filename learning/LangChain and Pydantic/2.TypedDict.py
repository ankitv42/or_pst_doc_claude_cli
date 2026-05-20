'''
As we have seen about pydantic, it is a powerful library for data validation and settings 
management using Python type annotations.

TypedDict, on the other hand, is a feature in Python that allows you to define a dictionary 
with specific keys and value types. It is part of the typing module and is used to create more structured and 
type-safe dictionaries.

The main purpose of TypedDict is to provide a way to specify the expected structure of a 
dictionary. This can be particularly useful for type checking and improving code readability.


First understand the problem it solves:
Suppose you write:

user = {
    "name": "Ankit",
    "age": 25
}

This is a perfectly valid Python dictionary. But what if you accidentally misspell "name" as 
"nmae"? 

Or

if you assign an integer to "name" instead of a string? Python won't complain until you 
try to access user["name"] and get a KeyError, or try to use user["name"] as a string and 
get a TypeError.

With TypedDict, you can define the expected structure of the dictionary upfront. This allows
you to catch these kinds of errors at the time of writing the code, rather than at runtime.

TypedDict lets you define:

“This dictionary MUST have these keys with these types.”

                    from typing import TypedDict

                    class User(TypedDict):
                        name: str
                        age: int

Now, if you try to create a User dictionary that doesn't match this structure, 
you'll get a type error:

Important Thing

Python itself usually DOES NOT stop execution.
TypedDict mainly helps:
    IDEs
    static type checkers
    autocomplete
    large team code quality

Tools like:
    mypy
    pyright
    VSCode

will warn you.

=================================================================================================================

Why AI Engineers use it heavily?

In AI systems, lots of data moves around as dictionaries.
Example:

state = {
    "messages": [...],
    "user_query": "...",
    "tool_output": "...",
    "next_step": "search"
}

Without structure, this becomes chaos.
So engineers define:

    from typing import TypedDict

    class AgentState(TypedDict):
        messages: list
        user_query: str
        tool_output: str
        next_step: str


Now everyone knows:
what exists
what type it is
what agent nodes can access

=========================================================================================================================================

TypedDict vs Pydantic

“TypedDict and Pydantic both define structure… so why both?”
But internally they solve different problems.

TypedDict is a static type hinting tool. It’s like a blueprint for your dictionaries. It helps you and your tools understand what keys and 
value types to expect. But it doesn’t do anything at runtime. It won’t stop you from creating a dictionary that doesn’t match the 
structure.

Pydantic, on the other hand, is a runtime data validation and parsing library. It not only defines the structure of your data but also 
enforces it.
When you create a Pydantic model, it will automatically validate the data you pass to it. If the data doesn’t match the expected types 
or structure, Pydantic will raise an error. It also has powerful features like type coercion, default values, and complex nested models.

In summary:
- TypedDict is for static type checking and improving code readability. Use it in your Internal code to define the expected structure.
- Pydantic is for runtime data validation and parsing. Use it at the boundaries of your system where you need to validate incoming data, 
  like LLM responses, API inputs, or configuration files.
'''