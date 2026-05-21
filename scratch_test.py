import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google import genai
import config

if __name__ == "__main__":
    keys = config.gemini_api_keys
    if not keys:
        print("No API keys found!")
        sys.exit(1)

    print(f"Loaded {len(keys)} key(s).")
    client = genai.Client(api_key=keys[0])

    try:
        print("Testing basic interaction...")
        # Using gemini-2.5-flash as default text model
        model = "gemini-2.5-flash"
        
        # Test simple text input
        interaction = client.interactions.create(
            model=model,
            input="Hello! How are you?"
        )
        print("Basic interaction ID:", interaction.id)
        print("Output text:", interaction.output_text)
        print("Steps in interaction:", len(interaction.steps))
        for step in interaction.steps:
            print(f" - Step: type={step.type}, status={step.status}")
            if hasattr(step, 'content') and step.content:
                for content_item in step.content:
                    print(f"   * Content item: type={content_item.type}")
                    if hasattr(content_item, 'text'):
                        print(f"     text: {content_item.text[:50]}...")

        print("\nTesting multi-turn interaction...")
        # Follow-up interaction using the previous interaction ID
        follow_up = client.interactions.create(
            model=model,
            previous_interaction_id=interaction.id,
            input="What was the first thing I said to you?"
        )
        print("Follow-up interaction ID:", follow_up.id)
        print("Output text:", follow_up.output_text)

    except Exception:
        import traceback
        traceback.print_exc()
