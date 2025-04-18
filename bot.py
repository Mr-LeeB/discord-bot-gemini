import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import google.generativeai as genai
from image_generator import generate_image_with_gemini
import threading
from flask import Flask

# Load biến môi trường
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Cấu hình Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")
# image_model = genai.GenerativeModel("gemini-2.0-flash-exp-image-generation")

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
    await bot.tree.sync()
    print(f"🤖 Bot đã sẵn sàng dưới tên: {bot.user}")


# Dict lưu chat session theo user
user_sessions = {}


@bot.tree.command(name="gemini", description="Đặt câu hỏi cho Gemini")
async def gemini_chat(interaction: discord.Interaction, prompt: str):
    allowed_channels = ["gemini-chat", "ask-gemini"]

    if interaction.channel.name not in allowed_channels:
        await interaction.response.send_message(
            f"❌ Lệnh này chỉ hoạt động trong các kênh: {', '.join(allowed_channels)}",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    try:
        user_id = interaction.user.id

        # Nếu user chưa có session, tạo mới
        if user_id not in user_sessions:
            user_sessions[user_id] = model.start_chat(history=[])

        chat = user_sessions[user_id]

        # Gửi câu hỏi và nhận phản hồi từ Gemini
        response = chat.send_message(prompt)
        reply = response.text

        MAX_LENGTH = 1900
        chunks = [reply[i:i+MAX_LENGTH]
                  for i in range(0, len(reply), MAX_LENGTH)]
        for chunk in chunks:
            await interaction.followup.send(chunk)

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {e}")


@bot.tree.command(name="reset_gemini", description="Xoá ngữ cảnh trò chuyện với Gemini của bạn")
async def reset_gemini(interaction: discord.Interaction):
    user_id = interaction.user.id

    if user_id in user_sessions:
        del user_sessions[user_id]
        await interaction.response.send_message("✅ Đã reset hội thoại với Gemini.")
    else:
        await interaction.response.send_message("ℹ️ Bạn chưa có hội thoại nào để reset.")


def refine_prompt_for_image(original_prompt: str) -> str:
    """Dùng Gemini để viết lại prompt tạo ảnh chi tiết hơn"""
    try:
        prompt = (
            "Tôi muốn bạn viết lại mô tả ảnh chi tiết và rõ ràng hơn từ câu sau, "
            "để có thể dùng với AI tạo ảnh. Chỉ trả về mô tả, không giải thích thêm. "
            "Nếu prompt viết bằng ngôn ngữ khác tiếng Việt, trả về prompt gốc.\n\n"
            f"Prompt gốc: {original_prompt}"
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Lỗi khi tạo prompt chi tiết: {e}")
        return original_prompt


@bot.tree.command(name="image", description="Tạo ảnh bằng Gemini từ mô tả văn bản")
async def generate_image_command(interaction: discord.Interaction, prompt: str):
    allowed_channels = ["gemini-chat", "ask-gemini", "gemini-images"]

    if interaction.channel.name not in allowed_channels:
        await interaction.response.send_message(
            f"❌ Lệnh này chỉ hoạt động trong các kênh: {', '.join(allowed_channels)}",
            ephemeral=True
        )
        return

    await interaction.response.defer()
    try:
        await interaction.followup.send("🎨 Gemini đang tạo ảnh, xin chờ chút...")

        # Cải thiện prompt
        detailed_prompt = refine_prompt_for_image(prompt)
        # Gọi hàm tạo ảnh từ image_generator
        image_data = generate_image_with_gemini(detailed_prompt)

        if image_data is None:
            await interaction.followup.send("❌ Không nhận được ảnh từ Gemini. Hãy thử mô tả khác rõ ràng hơn.")
            return

        # Gửi ảnh về cho người dùng
        file = discord.File(fp=image_data, filename="gemini_image.png")
        await interaction.followup.send(
            content=f"📷 Ảnh được tạo từ prompt: `{prompt}`\nPrompt chi tiết: `{detailed_prompt}`",
            file=file
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi khi tạo ảnh: {e}")

# Khởi chạy Flask + bot song song
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(DISCORD_TOKEN)
