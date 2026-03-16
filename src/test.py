import asyncio
from AI.graph import run_agent

async def main():
    conversation = []
    
    while True:
        user_input = input("You : ")

        if user_input.strip().lower() == "exit":
            break
        else:
            # Remove session_id since your run_agent doesn't accept it
            result = await run_agent(
                user_input=user_input,
                user_info={
                    "id": 3,
                    "role": "user",
                    "name": "krish",
                    "type": "user",
                    "owner_type": "user"
                },
                conversation_history=conversation,
                thread_id=1233423
                # Removed session_id
            )
            
            # Add to conversation history
            conversation.append({"role": "user", "content": user_input})
            conversation.append({"role": "assistant", "content": result})
            
            print(f"AI : {result}")
            print()

# Run the async function
if __name__ == "__main__":
    asyncio.run(main())