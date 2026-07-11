from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Jembatan ke server Fireworks
client = OpenAI(
    base_url=os.getenv("AMD_VISION_URL", "https://api.fireworks.ai/inference/v1"),
    api_key=os.getenv("FIREWORKS_API_KEY", os.getenv("OPENAI_API_KEY", ""))
)

print("🔍 Membongkar SELURUH isi server tanpa saringan...\n")

try:
    daftar_model = client.models.list()
    
    print("✅ INI DIA SEMUA MODEL YANG BISA KAMU PAKAI:")
    print("-" * 50)
    
    # Mencetak semua nama tanpa peduli gemma atau llama
    for model in daftar_model.data:
        print(f"-> {model.id}")
        
    print("-" * 50)

except Exception as e:
    print("❌ Gagal mengambil daftar:", e)