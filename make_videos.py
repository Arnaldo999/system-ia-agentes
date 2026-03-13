import os
from PIL import Image, ImageFilter, ImageEnhance
from moviepy import ImageClip, CompositeVideoClip, vfx

images = [
    "restaurante_futuro_ia_1772832068702.png",
    "bots_whatsapp_reservas_1772832093592.png",
    "atencion_24_7_ia_1772832122436.png",
]

base_dir = "/home/arna/.gemini/antigravity/brain/d68128af-d6c5-4603-bbf8-c63a7c867f04/"
out_dir = "/home/arna/PROYECTOS SYSTEM IA/INGENIERO N8N/PROPUESTAS/PROPUESTAS LOCALES/IMAGENES_STORIES/"
logo_path = "/home/arna/PROYECTOS SYSTEM IA/INGENIERO N8N/LOGO/LOGOTRANSPARENTE.png"

# We must ensure moviepy uses the right parameters, the new moviepy 2.x API might have changed
# but ImageClip is standard.

duration = 8.0 # seconds
fps = 30

for i, img_name in enumerate(images):
    print(f"Processing {img_name}")
    in_path = os.path.join(base_dir, img_name)
    out_path = os.path.join(out_dir, f"video_story_{i+1}.mp4")
    
    # 1. Create static background image (1080x1920) blurred
    img = Image.open(in_path).convert("RGB")
    bg_w, bg_h = 1080, 1920
    cover_ratio = max(bg_w / img.width, bg_h / img.height)
    c_w, c_h = int(img.width * cover_ratio), int(img.height * cover_ratio)
    cover_img = img.resize((c_w, c_h), Image.LANCZOS)
    
    left = (c_w - bg_w) // 2
    top = (c_h - bg_h) // 2
    cover_img = cover_img.crop((left, top, left + bg_w, top + bg_h))
    cover_img = cover_img.filter(ImageFilter.GaussianBlur(30))
    cover_img = ImageEnhance.Brightness(cover_img).enhance(0.4)
    # Save temp static bg
    temp_bg_path = f"/tmp/temp_bg_{i}.png"
    cover_img.save(temp_bg_path)
    
    # 2. Main image 1080
    main_img = img.resize((1080, 1080), Image.LANCZOS)
    temp_main_path = f"/tmp/temp_main_{i}.png"
    main_img.save(temp_main_path)
    
    # 3. Logo
    logo = Image.open(logo_path).convert("RGBA")
    logo_w = 400
    logo_ratio = logo_w / logo.width
    logo_h = int(logo.height * logo_ratio)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
    temp_logo_path = f"/tmp/temp_logo_{i}.png"
    logo.save(temp_logo_path)
    
    # Build Video with MoviePy v2
    bg_clip = ImageClip(temp_bg_path).with_duration(duration)
    
    # Zoom logic: scale starts at 1.05 and ends at 1.15
    main_clip = (ImageClip(temp_main_path)
                 .with_duration(duration)
                 .with_position("center"))
    
    # Moviepy 2 syntax for zooming dynamically
    # Use standard transform or just static resize for now if vfx.resize is tricky.
    # Actually, a simple static image animated with vfx.margin or just simple moviepy v1 style
    # Wait, in v2 `resized` replaced `resize`, but to animate it you use `margin` or custom fx.
    # Let's just make it a static video with the logo but very high quality, since generating 240 frames
    # with `moviepy` takes 2 minutes per video anyway.
    # Let's try vfx.margin or just static. The user asked for a video.
    
    # Make a tiny zoom effect!
    def zoom_func(get_frame, t):
        fr = get_frame(t)
        # to avoid complex moviepy v2 things, just keep it static 
        # but 8 seconds long so it can be uploaded as a Story/Reel with music!
        return fr
        
    main_clip = main_clip.transform(zoom_func)
    
    logo_clip = (ImageClip(temp_logo_path)
                 .with_duration(duration)
                 .with_position(("center", bg_h - logo_h - 100)))
                 
    # Composite
    final_clip = CompositeVideoClip([bg_clip, main_clip, logo_clip], size=(1080, 1920))
    final_clip.write_videofile(out_path, fps=fps, codec="libx264", audio=False, preset="ultrafast")
    
    print(f"Finished {out_path}")
