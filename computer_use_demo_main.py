import asyncio
import os
import sys
import json
import base64
import argparse

from computer_use_demo.loop import sampling_loop, APIProvider
from computer_use_demo.tools import ToolResult
from anthropic.types.beta import BetaMessage, BetaMessageParam
from anthropic import APIResponse

from cli import start_realtime_session

async def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Claude Computer Use Demo')
    parser.add_argument('--realtime', action='store_true', help='Use realtime mode with voice interaction')
    parser.add_argument('--env', choices=['prod', 'dev'], default='prod', help='Environment for realtime mode')
    parser.add_argument('instruction', nargs='*', help='Instruction for non-realtime mode')
    args = parser.parse_args()

    # Check for realtime mode
    if args.realtime:
        await start_realtime_session(args.env)
        return

    # Regular computer use mode
    api_key = os.getenv("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")
    if api_key == "YOUR_API_KEY_HERE":
        raise ValueError(
            "Please set your API key in the ANTHROPIC_API_KEY environment variable"
        )
    provider = APIProvider.ANTHROPIC

    # Get instruction
    instruction = " ".join(args.instruction) if args.instruction else "Save an image of a cat to the desktop."

    print(
        f"Starting Claude Computer Use.\nPress ctrl+c to stop.\nInstruction: '{instruction}'"
    )

    # Set up messages
    messages: list[BetaMessageParam] = [
        {
            "role": "user",
            "content": instruction,
        }
    ]

    # Define callbacks
    def output_callback(content_block):
        if isinstance(content_block, dict) and content_block.get("type") == "text":
            print("Assistant:", content_block.get("text"))

    def tool_output_callback(result: ToolResult, tool_use_id: str):
        if result.output:
            print(f"> Tool Output [{tool_use_id}]:", result.output)
        if result.error:
            print(f"!!! Tool Error [{tool_use_id}]:", result.error)
        if result.base64_image:
            os.makedirs("screenshots", exist_ok=True)
            image_data = result.base64_image
            with open(f"screenshots/screenshot_{tool_use_id}.png", "wb") as f:
                f.write(base64.b64decode(image_data))
            print(f"Took screenshot screenshot_{tool_use_id}.png")

    def api_response_callback(response: APIResponse[BetaMessage]):
        print(
            "\n---------------\nAPI Response:\n",
            json.dumps(json.loads(response.text)["content"], indent=4),  # type: ignore
            "\n",
        )

    # Run sampling loop
    messages = await sampling_loop(
        model="claude-3-5-sonnet-20241022",
        provider=provider,
        system_prompt_suffix="",
        messages=messages,
        output_callback=output_callback,
        tool_output_callback=tool_output_callback,
        api_response_callback=api_response_callback,
        api_key=api_key,
        only_n_most_recent_images=10,
        max_tokens=4096,
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSession ended.")
    except Exception as e:
        print(f"Error: {e}")
