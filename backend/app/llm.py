from langchain_ollama import OllamaLLM  # pyright: ignore[reportMissingImports]

ollama_llm = OllamaLLM(
    base_url="http://127.0.0.1:11434",  # default Ollama endpoint
    model="llama3.2",  # Using llama3.2
)