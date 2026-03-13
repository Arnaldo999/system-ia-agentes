from PIL import Image, ImageFilter, ImageEnhance
import os

images = [
    "restaurante_futuro_ia_1772832068702.png",
    "bots_whatsapp_reservas_1772832093592.png",
    "atencion_24_7_ia_1772832122436.png",
    "delivery_automatico_1772832153837.png",
    "voz_ia_telefono_1772832187930.png",
    "traductor_turistas_1772832227345.png",
    "resenas_automaticas_1772832271200.png",
    "reservas_vacias_1772832316122.png",
    "dashboard_control_1772832367889.png",
    "notificacion_push_1772832418004.png",
    "chef_ia_1772832486863.png",
    "error_humano_1772832547220.png",
    "menu_interactivo_1772832609568.png",
    "call_to_action_restaurantes_1772832679603.png",
    "idiomas_instantaneos_1772832749863.png",
    "ahorro_tiempo_1772832822849.png"
]

base_dir = "/home/arna/.gemini/antigravity/brain/d68128af-d6c5-4603-bbf8-c63a7c867f04/"
logo_path = "/home/arna/PROYECTOS SYSTEM IA/INGENIERO N8N/LOGO/LOGOTRANSPARENTE.png"

try:
    logo = Image.open(logo_path).convert("RGBA")
    logo_w = 400
    logo_ratio = logo_w / logo.width
    logo_h = int(logo.height * logo_ratio)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
except Exception as e:
    print(f"Error loading logo: {e}")
    logo = None

new_images = []

for img_name in images:
    path = os.path.join(base_dir, img_name)
    if not os.path.exists(path):
        continue
    try:
        img = Image.open(path).convert("RGBA")
        
        # Create story background (1080x1920)
        bg_w, bg_h = 1080, 1920
        story_bg = Image.new("RGBA", (bg_w, bg_h), (0, 0, 0, 255))
        
        # Resize image for background to cover
        cover_ratio = max(bg_w / img.width, bg_h / img.height)
        c_w = int(img.width * cover_ratio)
        c_h = int(img.height * cover_ratio)
        cover_img = img.resize((c_w, c_h), Image.LANCZOS)
        
        # Crop center
        left = (c_w - bg_w) // 2
        top = (c_h - bg_h) // 2
        cover_img = cover_img.crop((left, top, left + bg_w, top + bg_h))
        
        # Blur and darken
        cover_img = cover_img.filter(ImageFilter.GaussianBlur(30))
        enhancer = ImageEnhance.Brightness(cover_img)
        cover_img = enhancer.enhance(0.4)
        
        story_bg.paste(cover_img, (0, 0))
        
        # Main image in center (1080x1080)
        main_img = img.resize((1080, 1080), Image.LANCZOS)
        main_y = (bg_h - 1080) // 2
        story_bg.paste(main_img, (0, main_y), main_img)
        
        # Paste logo at bottom
        if logo:
            logo_x = (bg_w - logo_w) // 2
            logo_y = bg_h - logo_h - 100
            story_bg.paste(logo, (logo_x, logo_y), logo)
            
        # Save
        out_name = img_name.replace(".png", "_story.png")
        out_path = os.path.join(base_dir, out_name)
        
        # Convert back to RGB to save as PNG or JPEG without huge size
        final_rgb = story_bg.convert("RGB")
        final_rgb.save(out_path, "PNG", optimize=True)
        print(f"Saved {out_path}")
        new_images.append(out_name)
    except Exception as e:
        print(f"Error processing {img_name}: {e}")

print("Done processing successfully.")
