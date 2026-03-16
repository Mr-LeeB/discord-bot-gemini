import os
import sys
import logging
import asyncio
import time
from dotenv import load_dotenv

import discord
from discord.ext import commands
from aiohttp import web
from google import genai

from image_generator import generate_image_with_gemini

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger("DiscordBot")

# Load biến môi trường
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN or not GEMINI_API_KEY:
    logger.error("Thiếu DISCORD_TOKEN hoặc GEMINI_API_KEY trong file .env")
    sys.exit(1)

# Khởi tạo Gemini Client dùng SDK mới 'google-genai'
try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Khởi tạo Gemini Client thất bại: {e}")
    sys.exit(1)

# Khởi tạo Discord Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Quản lý Session Tránh Memory Leak
class ChatSessionManager:
    def __init__(self, ttl_seconds: int = 3600):
        self.sessions = {}
        self.ttl = ttl_seconds
        
    def get_or_create(self, user_id: int):
        now = time.time()
        # Clean expired sessions first
        self._cleanup(now)
        
        if user_id not in self.sessions:
            chat = gemini_client.chats.create(model="gemini-1.5-flash")
            self.sessions[user_id] = {"chat": chat, "last_active": now}
        else:
            self.sessions[user_id]["last_active"] = now
            
        return self.sessions[user_id]["chat"]
        
    def delete(self, user_id: int) -> bool:
        if user_id in self.sessions:
            del self.sessions[user_id]
            return True
        return False
        
    def _cleanup(self, now: float):
        expired = [uid for uid, data in self.sessions.items() if now - data["last_active"] > self.ttl]
        for uid in expired:
            del self.sessions[uid]

# 1 giờ TTL để clear session nếu user không chat tiếp
session_manager = ChatSessionManager(ttl_seconds=3600) 

@bot.event
async def on_ready():
    await bot.tree.sync()
    logger.info(f"🤖 Bot đã sẵn sàng dưới tên: {bot.user}")

@bot.tree.command(name="gemini", description="Đặt câu hỏi cho Gemini")
async def gemini_chat(interaction: discord.Interaction, prompt: str):
    allowed_channels = ["gemini-chat", "ask-gemini"]

    # Optional: kiểm tra hasattr cho channel name vì DM channel không có name
    channel_name = getattr(interaction.channel, 'name', '')
    if channel_name not in allowed_channels and interaction.guild is not None:
        await interaction.response.send_message(
            f"❌ Lệnh này chỉ hoạt động trong các kênh: {', '.join(allowed_channels)}",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    try:
        chat = session_manager.get_or_create(interaction.user.id)
        
        # Gửi tin nhắn qua genai SDK
        response = chat.send_message(prompt)
        reply = response.text or "Không có phản hồi từ Gemini."

        # Xử lý giới hạn ký tự Discord (2000 là max, dùng 1900 cho an toàn)
        MAX_LENGTH = 1900
        chunks = [reply[i:i+MAX_LENGTH] for i in range(0, len(reply), MAX_LENGTH)]
        for chunk in chunks:
            await interaction.followup.send(chunk)

    except Exception as e:
        logger.error(f"Lỗi khi chat Gemini: {e}")
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            friendly_msg = "❌ Ôi chu choa, API Key của mình đang bị giới hạn (hết lượt dùng / Rate Limit). Anh thử lại sau vào ngày mai hoặc đổi API Key khác nha!"
        else:
            friendly_msg = ("❌ Có lỗi rùi. Xin vui lòng thử lại sau nhé!")
        await interaction.followup.send(friendly_msg)

@bot.tree.command(name="reset_gemini", description="Xoá ngữ cảnh trò chuyện với Gemini của bạn")
async def reset_gemini(interaction: discord.Interaction):
    if session_manager.delete(interaction.user.id):
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
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Lỗi khi tạo hình mẫu prompt chi tiết: {e}")
        return original_prompt

@bot.tree.command(name="image", description="Tạo ảnh bằng Gemini từ mô tả văn bản")
async def generate_image_command(interaction: discord.Interaction, prompt: str):
    allowed_channels = ["gemini-chat", "ask-gemini", "gemini-images"]

    channel_name = getattr(interaction.channel, 'name', '')
    if channel_name not in allowed_channels and interaction.guild is not None:
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
        
        # Gọi hàm tạo ảnh từ image_generator, truyền client vào
        image_data = generate_image_with_gemini(gemini_client, detailed_prompt)

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
        logger.error(f"Lỗi khi tạo ảnh: {e}")
        await interaction.followup.send("❌ Đã xảy ra lỗi khi tạo ảnh. Vui lòng thử lại sau.")

# Thiết lập aiohttp web server để nhận ping từ Render, thay thế cho Flask
async def web_server():
    app = web.Application()
    app.router.add_get('/', lambda request: web.Response(text="✅ Gemini Discord Bot is running (aiohttp)!"))
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 aiohttp server running on port {port}")

async def main():
    # Khởi động web server song song trên cùng Event Loop
    asyncio.create_task(web_server())
    
    # Khởi động discord bot
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
