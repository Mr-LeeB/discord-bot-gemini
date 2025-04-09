import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")


class GeminiBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()  # Sync slash commands với Discord


bot = GeminiBot()


@bot.event
async def on_ready():
    print(f"✅ Bot đã sẵn sàng dưới tên: {bot.user}")


@bot.tree.command(name="gemini", description="Đặt câu hỏi cho Gemini bằng tiếng Việt")
async def gemini_chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()  # gửi trạng thái đang xử lý
    try:
        response = model.generate_content(prompt)
        reply = response.text

        if len(reply) > 1900:
            reply = reply[:1900] + "..."

        await interaction.followup.send(reply)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi khi gọi Gemini: {e}")

bot.run(DISCORD_TOKEN)
