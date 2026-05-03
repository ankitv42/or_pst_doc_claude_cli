'''
Pydantic has fundamentally changed how we handle data validation in Python by moving away from "dictionary-soup" 
and toward Data Contracts. In a high-scale production environment, you don't just want data; you want guaranteed 
data.

Think of Pydantic as the "Gatekeeper" of your application. It ensures that every piece of data entering your system is 
type-safe, validated, and structured before it ever touches your business logic.

Pydantic is a Python library that lets you define data structures with types and automatic validation. Think of it 
as a smarter, stricter version of a Python dictionary.



1. The Core Philosophy: Parse, Don't Validate
    Instead of just checking if data is valid, it transforms.
    
    Pydantic uses Type Hinting to "coerce" data into the correct type. If you pass a string "123" to an integer field
    Pydantic doesn't just check it—it converts it. If it can't, it throws a structured error.

2.  creating a configuration class

    Suppose you have bunch of settings for your application, like database URL, API keys, etc. You can define a 
    Pydantic model to hold these settings, and it will automatically validate them when you create an instance.

    so in 10 different python file you need not to write all the variable (url, keys etc). you can just import
    the configuration class and use it. This promotes DRY (Don't Repeat Yourself) principles and centralizes your 
    configuration management.

    from pydantic import BaseModel
    class AppConfig(BaseModel):
        database_url: str = "sqlite:///mydb.sqlite"
        api_key: str = "ghfhfhu6756757"
        debug_mode: bool = False  # default value


    In 10 files you can just import AppConfig and use it. 

    config = AppConfig()
    fetch_data(config.database_url, config.api_key)
    push_notification(config.debug_mode)

'''

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional
from datetime import datetime

class UserSchema(BaseModel):
    # Basic types with constraints
    user_id: int
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

    # Optional fields with defaults
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


    # Nested models
    friends: Optional[List[str]] = None

# usage
raw_data = {
    "user_id": "123",  # Will be coerced to int
    "username": "john_doe",
    "email": "ankitv42@gmail.com",
    "friends": ["rishi", "dashrath"]  # Will be coerced to List[str]
}

user = UserSchema(**raw_data)
print(user)