
async def groq_AI_chatting(message: aiogram_types.Message, SYSTEM_INSTRUCTION, client):
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user",   "content": message.text},
            ],
            model="llama-3.3-70b-versatile",
        )
        await message.answer(response.choices[0].message.content)
    except Exception as e:
        print(f"Groq error: {e}")
        await message.answer("Sorry, I had trouble processing that. Could you try again?")