import os
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# Lấy API key từ biến môi trường
api_key = os.getenv("GEMINI_IMAGE_API_KEY")

# Khởi tạo client với API key từ biến môi trường
client = genai.Client(api_key=api_key)


def generate_image_with_gemini(prompt: str) -> BytesIO | None:
    try:
        # Gửi yêu cầu tạo ảnh từ Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE']
            )
        )

        # Xử lý kết quả trả về từ Gemini
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                # Nếu Gemini trả về văn bản, trả về gợi ý mô tả
                print("⚠️ Gemini gợi ý mô tả:", part.text)
                return None
            elif part.inline_data is not None:
                # Nếu Gemini trả về hình ảnh, chuyển đổi và trả về
                image = Image.open(BytesIO(part.inline_data.data))
                image_io = BytesIO()
                image.save(image_io, 'PNG')
                image_io.seek(0)
                return image_io

        return None

    except Exception as e:
        print(f"❌ Lỗi khi tạo ảnh: {e}")
        return None
