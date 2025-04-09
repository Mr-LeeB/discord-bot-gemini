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


@bot.command(name="gemini")
async def gemini_chat(ctx, *, prompt: str):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.reply("❌ Lệnh này chỉ hoạt động trong server Discord.")
        return

    await ctx.trigger_typing()
    try:
        response = model.generate_content(prompt)
        reply = response.text

        if len(reply) > 1900:
            reply = reply[:1900] + "..."

        await ctx.reply(reply)
    except Exception as e:
        await ctx.reply("❌ Lỗi khi gọi Gemini: " + str(e))

# Khởi chạy Flask + bot song song
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(DISCORD_TOKEN)
