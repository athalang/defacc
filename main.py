import litellm

from settings import settings

def main():
    response = litellm.completion(
        model=settings.model,
        messages=[{"role": "user", "content": "Whats your name?"}],
        api_base=settings.api_base,
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
