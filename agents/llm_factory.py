"""
ORCA — agents/llm_factory.py
=============================
Returns the correct LLM object based on LLM_PROVIDER in .env
 
One function: get_llm()
Every file that needs an LLM calls this.
Change LLM_PROVIDER in .env — entire system switches provider.
 
Supported providers:
    groq     → llama-3.1-8b-instant (free, fast, recommended for dev)
    openai   → gpt-4o-mini (paid, higher quality)
    ollama   → llama3 (free, runs locally, no internet needed)
 
.env setup:
    LLM_PROVIDER=groq
    GROQ_API_KEY=your-key-here
 
    LLM_PROVIDER=openai
    OPENAI_API_KEY=your-key-here
 
    LLM_PROVIDER=ollama
    (no key needed — Ollama runs locally)
 
Usage:
    from agents.llm_factory import get_llm
    llm = get_llm()
"""

import os
from dotenv import load_dotenv

load_dotenv()

def get_llm():
    """
    Returns the configured LLM based on LLM_PROVIDER env var.
 
    Raises ValueError if LLM_PROVIDER is not set or unsupported.
    Raises ImportError if the required package is not installed.
    """
    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()

    # ── Groq (free, recommended for development) ──────────────────────────

    if provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError:
            raise ImportError("langchain-groq not installed. Run: pip install langchain-groq.")
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env.")
        
        return ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"), 
            api_key=api_key, 
            temperature=0
            )

    # ── OpenAI ────────────────────────────────────────────────────────────
    elif provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai not installed. Run: pip install langchain-openai"
            )
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in .env")
 
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=api_key,
        )
 
    # ── Ollama (local, no API key needed) ─────────────────────────────────
    elif provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            raise ImportError(
                "langchain-ollama not installed. Run: pip install langchain-ollama"
            )
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3"),
            temperature=0,
        )
 
    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: '{provider}'. "
            f"Choose from: groq, openai, ollama"
        )
    
def get_provider_name():
    """
    Returns the name of the currently configured LLM provider. Used for logging.
    """
    return os.getenv("LLM_PROVIDER", "groq").lower().strip()

def get_model_name():
    """
    Returns the name of the currently configured LLM model. Used for logging.
    """
    provider = get_provider_name()
    if provider == "groq":
        return os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    elif provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    elif provider == "ollama":
        return os.getenv("OLLAMA_MODEL", "llama3")
    else:
        return "unknown-model"


# ── quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing LLM Factory...")

    provier = get_provider_name()
    model = get_model_name()
    print(f"Configured LLM Provider: {provier}")
    print(f"Configured LLM Model: {model}")

    print(f"\nLoading LLM...")
    llm = get_llm()
    print(f"LLM loaded successfully: {llm}")
    print(f"LLM object: {type(llm).__name__}")

    print(f"\nSending test message...")
    response = llm.invoke(
        "You are an inventory analyst. "
        "In one sentence, what is the most important metric to track "
        "for retail inventory management?"
    )
    print(f"\nResponse: {response.content}")
    print(f"\nllm_factory working correctly.\n")