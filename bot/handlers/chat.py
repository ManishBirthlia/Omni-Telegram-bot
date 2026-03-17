
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

async def nvidia_AI_chatting(message: aiogram_types.Message, SYSTEM_INSTRUCTION, client):
    try:
        completion = nvidia_client.chat.completions.create(
        model="nvidia/nemotron-3-nano-30b-a3b",
        messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user",   "content": message.text},
            ],
        temperature=1,
        top_p=1,
        max_tokens=16384,
        extra_body={"reasoning_budget":16384,"chat_template_kwargs":{"enable_thinking":True}},
        stream=True
        )
        for chunk in completion:
            if not chunk.choices:
                continue
            reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
            if reasoning:
                await message.answer(reasoning)
            if chunk.choices[0].delta.content is not None:
                await message.answer(chunk.choices[0].delta.content)
    except Exception as e:
        print(f"error: {e}")
        await message.answer("Sorry, I had trouble processing that. Could you try again?")