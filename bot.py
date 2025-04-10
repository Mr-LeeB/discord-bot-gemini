import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import google.generativeai as genai
import threading
from flask import Flask

# Load biến môi trường
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Cấu hình Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Setup Flask giả để Render thấy có cổng mở
app = Flask(__name__)


@app.route("/")
def home():
    return "✅ Gemini Discord Bot is running!"


def run_web():
    port = int(os.environ.get("PORT", 10000))  # Render sẽ truyền PORT
    print(f"🌐 Flask server running on port {port}")
    app.run(host="0.0.0.0", port=port)


# Tạo bot
intents = discord.Intents.default()
intents.message_content = True  # Bắt buộc để đọc message
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"🤖 Bot đã sẵn sàng dưới tên: {bot.user}")


@bot.tree.command(name="gemini", description="Đặt câu hỏi cho Gemini")
async def gemini_chat(interaction: discord.Interaction, prompt: str):
    # Tên các channel được phép
    allowed_channels = ["gemini-chat", "ask-gemini"]

    # Kiểm tra channel
    if interaction.channel.name not in allowed_channels:
        await interaction.response.send_message(
            f"❌ Lệnh này chỉ hoạt động trong các kênh: {', '.join(allowed_channels)}",
            ephemeral=True  # chỉ người dùng thấy
        )
        return

    await interaction.response.defer()

    try:
        response = model.generate_content(prompt)
        reply = response.text
        MAX_LENGTH = 1900
        chunks = [reply[i:i+MAX_LENGTH]
                  for i in range(0, len(reply), MAX_LENGTH)]
        for chunk in chunks:
            await interaction.followup.send(chunk)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {e}")

# Khởi chạy Flask + bot song song
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(DISCORD_TOKEN)
