import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Script2Cinema AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_DIR = Path(__file__).parent
OUTPUT_DIR = APP_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

FPS = 24
WIDTH = 1280
HEIGHT = 720
VIDEO_PRESET = "veryfast"
VIDEO_CRF = "28"


# ============================================================
# SCRIPT ANALYSIS
# ============================================================

def detect_scenes(script: str):
    """Robustly detect Scene/INT/EXT/Chapter headings."""
    if not script.strip():
        return []

    pattern = re.compile(
        r"(?im)^\s*(?:"
        r"scene\s*(?:[-:#]?\s*)\d+(?:\s*[-:#—]\s*.*)?"
        r"|int\.\s*.*"
        r"|ext\.\s*.*"
        r"|chapter\s*(?:[-:#]?\s*)\d+(?:\s*[-:#—]\s*.*)?"
        r"|سین\s*(?:[-:#]?\s*)\d+(?:\s*[-:#—]\s*.*)?"
        r"|منظر\s*(?:[-:#]?\s*)\d+(?:\s*[-:#—]\s*.*)?"
        r")\s*$"
    )

    matches = list(pattern.finditer(script))
    if matches:
        scenes = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(script)
            title = match.group(0).strip()
            scenes.append({
                "number": i + 1,
                "title": title,
                "text": script[start:end].strip(),
            })
        return scenes

    # Fallback: split on blank-line groups.
    blocks = [
        b.strip()
        for b in re.split(r"\n\s*\n\s*\n+", script)
        if b.strip()
    ]
    if not blocks:
        blocks = [script.strip()]

    return [
        {"number": i + 1, "title": f"Scene {i + 1}", "text": block}
        for i, block in enumerate(blocks)
    ]


IGNORED_LABELS = {
    "visual", "visuals", "camera", "music", "sound", "sfx",
    "action", "description", "narrator", "voiceover", "voice over",
    "location", "lighting", "shot", "direction", "note",
}

def detect_characters(script: str):
    """Detect speaker labels without treating production labels as characters."""
    found = []
    patterns = [
        r"(?m)^\s*([A-Za-z][A-Za-z0-9 _'-]{0,35})\s*:\s+.+$",
        r"(?m)^\s*([A-Za-z][A-Za-z0-9 _'-]{0,35})\s*-\s+.+$",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, script):
            name = re.sub(r"\s+", " ", match.group(1)).strip()
            if name.lower() in IGNORED_LABELS:
                continue
            if len(name) < 2 or name not in found:
                found.append(name)

    return found


def count_dialogues(script: str):
    pattern = r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{0,35}\s*:\s+.+$"
    return len(re.findall(pattern, script))


def estimate_duration(script: str):
    words = len(re.findall(r"\b[\w'-]+\b", script))
    return words / 120 if words else 0


def clean_dialogue_text(text: str):
    text = re.sub(
        r"(?im)^\s*(?:scene\s*(?:[-:#]?\s*)\d+.*|int\..*|ext\..*|"
        r"chapter\s*(?:[-:#]?\s*)\d+.*|سین\s*(?:[-:#]?\s*)\d+.*|"
        r"منظر\s*(?:[-:#]?\s*)\d+.*)$",
        "",
        text,
    )

    # Remove common production lines.
    cleaned = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(
            r"(?i)^(visual|camera|music|sound|sfx|action|description|"
            r"lighting|shot|location|direction|note)\s*[:\-]",
            stripped,
        ):
            continue
        cleaned.append(stripped)

    text = "\n".join(cleaned)
    text = re.sub(
        r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{0,35}\s*[:\-]\s*",
        "",
        text,
    )
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def scene_visual_prompt(scene):
    """Create a keyword-based visual description for local cinematic artwork."""
    raw = f"{scene['title']} {scene['text']}".lower()

    setting = "ancient dark-fantasy mountain kingdom, medieval stone architecture"
    atmosphere = "cinematic fog, rain mist, dramatic clouds, volumetric light"
    subject = "mysterious travelers and ancient ruins"

    if any(k in raw for k in ["forest", "jungle", "woods", "جنگل"]):
        setting = "ancient forbidden forest, enormous twisted trees, mossy ruins"
        atmosphere = "dense fog, moonlight shafts, drifting particles, eerie atmosphere"
        subject = "two young travelers moving cautiously through the forest"

    elif any(k in raw for k in ["ruin", "temple", "door", "دروازہ", "کھنڈر"]):
        setting = "ancient ruined temple carved into a mountain, gigantic stone doorway"
        atmosphere = "blue-black shadows, torchlight, floating dust, supernatural mist"
        subject = "three fantasy characters facing an ancient sealed doorway"

    elif any(k in raw for k in ["city", "kingdom", "ریاست", "شہر"]):
        setting = "hidden ancient fantasy city below a mountain cliff, massive stone towers"
        atmosphere = "night fog, thousands of tiny warm lights, dark blue sky"
        subject = "three travelers overlooking a forgotten kingdom"

    elif any(k in raw for k in ["sky", "storm", "آسمان", "بارش"]):
        setting = "ancient mountain kingdom at night, towering stone walls and rooftops"
        atmosphere = "violent storm, black clouds, rain, a supernatural crack in the sky"
        subject = "a frightened village watching an impossible event above the mountains"

    elif any(k in raw for k in ["creature", "monster", "hollow", "دیو", "مخلوق"]):
        setting = "ancient mountain ruins surrounded by darkness"
        atmosphere = "heavy fog, dust, cold moonlight, supernatural darkness"
        subject = "a huge shadowy creature partially hidden behind stone walls, glowing eyes"

    return (
        f"{setting}; {atmosphere}; {subject}; "
        "dark fantasy film still, realistic cinematic concept art, "
        "epic scale, detailed textures, dramatic composition, "
        "deep depth of field, no text, no logo, no watermark"
    )


# ============================================================
# SYSTEM
# ============================================================

def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


def run_command(command):
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


# ============================================================
# FREE LOCAL CINEMATIC ART
# ============================================================

def _font(size, bold=False):
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def create_cinematic_visual(scene, output_file, width=WIDTH, height=HEIGHT):
    """
    Creates a procedural cinematic fantasy background locally.
    No API key and no app watermark required.
    """
    from PIL import Image, ImageDraw

    raw = f"{scene['title']} {scene['text']}".lower()

    img = Image.new("RGB", (width, height))
    px = img.load()

    # Dark blue cinematic gradient.
    for y in range(height):
        t = y / max(1, height - 1)
        for x in range(width):
            radial = math.sqrt(
                ((x - width * 0.5) / width) ** 2
                + ((y - height * 0.42) / height) ** 2
            )
            glow = max(0, 1 - radial * 2.2)
            r = int(5 + 18 * glow + 5 * (1 - t))
            g = int(8 + 20 * glow + 6 * (1 - t))
            b = int(18 + 40 * glow + 10 * (1 - t))
            px[x, y] = (r, g, b)

    draw = ImageDraw.Draw(img, "RGBA")

    # Moon / supernatural light.
    moon_x, moon_y = int(width * 0.78), int(height * 0.22)
    moon_r = 70
    for radius in range(moon_r + 35, moon_r, -2):
        alpha = max(0, int(35 * (moon_r + 35 - radius) / 35))
        draw.ellipse(
            (moon_x-radius, moon_y-radius, moon_x+radius, moon_y+radius),
            fill=(180, 205, 255, alpha),
        )
    draw.ellipse(
        (moon_x-moon_r, moon_y-moon_r, moon_x+moon_r, moon_y+moon_r),
        fill=(210, 220, 235, 210),
    )

    # Mountains.
    mountain_color = (5, 7, 13, 255)
    points = [
        (0, height * .72),
        (width * .12, height * .49),
        (width * .23, height * .68),
        (width * .38, height * .40),
        (width * .52, height * .68),
        (width * .67, height * .45),
        (width * .82, height * .66),
        (width, height * .50),
        (width, height),
        (0, height),
    ]
    draw.polygon(points, fill=mountain_color)

    # Distant second mountain layer.
    points2 = [
        (0, height * .78), (width * .18, height * .60),
        (width * .33, height * .75), (width * .50, height * .55),
        (width * .70, height * .75), (width * .88, height * .57),
        (width, height * .70), (width, height), (0, height)
    ]
    draw.polygon(points2, fill=(10, 12, 20, 255))

    # Ancient city / village lights.
    for i in range(26):
        x = int((i * 47 + 31) % width)
        y = int(height * (0.62 + ((i * 17) % 18) / 100))
        draw.rectangle((x, y, x + 5, y + 8), fill=(240, 180, 70, 190))

    # Scene-specific supernatural sky crack.
    if any(k in raw for k in ["sky", "آسمان", "crack", "split", "پھٹ"]):
        crack = [
            (int(width*.62), 0),
            (int(width*.59), int(height*.18)),
            (int(width*.65), int(height*.31)),
            (int(width*.57), int(height*.47)),
            (int(width*.61), int(height*.60)),
        ]
        draw.line(crack, fill=(155, 185, 255, 180), width=8)
        draw.line(crack, fill=(225, 235, 255, 220), width=2)

    # Forest silhouettes.
    if any(k in raw for k in ["forest", "جنگل"]):
        for x in range(30, width, 70):
            top = int(height * (.43 + ((x * 13) % 80) / 1000))
            draw.polygon(
                [(x, height*.84), (x+30, top), (x+60, height*.84)],
                fill=(3, 10, 9, 255),
            )

    # Creature silhouette, kept partial rather than explicit.
    if any(k in raw for k in ["creature", "monster", "hollow", "مخلوق", "دیو"]):
        cx, cy = int(width*.72), int(height*.58)
        draw.ellipse((cx-110, cy-150, cx+110, cy+150), fill=(2, 2, 5, 220))
        draw.ellipse((cx-75, cy-100, cx+75, cy+20), fill=(1, 1, 3, 245))
        draw.ellipse((cx-42, cy-48, cx-22, cy-28), fill=(255, 190, 70, 230))
        draw.ellipse((cx+22, cy-48, cx+42, cy-28), fill=(255, 190, 70, 230))

    # Fog bands.
    for y in range(int(height*.58), height, 18):
        alpha = 18 + int(18 * (y / height))
        draw.rectangle((0, y, width, y+18), fill=(170, 185, 210, alpha))

    # Subtle cinematic vignette.
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    opx = overlay.load()
    for y in range(height):
        for x in range(width):
            dx = (x - width/2) / (width/2)
            dy = (y - height/2) / (height/2)
            d = min(1, math.sqrt(dx*dx + dy*dy))
            a = int(max(0, (d - .45) * 115))
            opx[x, y] = (0, 0, 0, a)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img.save(output_file, quality=94)


# ============================================================
# TTS + SCENE VIDEO
# ============================================================

def generate_voice(text, output_file, voice):
    try:
        import asyncio
        import edge_tts

        async def create_audio():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_file))

        asyncio.run(create_audio())
        return output_file.exists() and output_file.stat().st_size > 0
    except Exception:
        return False


def render_scene(scene, duration, temp_directory, voice_name):
    n = scene["number"]
    image_file = Path(temp_directory) / f"scene_{n:03d}.jpg"
    video_file = Path(temp_directory) / f"scene_{n:03d}.mp4"
    audio_file = Path(temp_directory) / f"scene_{n:03d}.mp3"

    dialogue = clean_dialogue_text(scene["text"])
    create_cinematic_visual(scene, image_file)

    has_audio = bool(dialogue) and generate_voice(
        dialogue[:14000], audio_file, voice_name
    )

    # Ken Burns style movement gives a still image cinematic motion.
    zoom_dir = "in" if n % 2 else "out"
    if zoom_dir == "in":
        zoom = "zoompan=z='min(zoom+0.0008,1.10)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    else:
        zoom = "zoompan=z='max(1.10-on*0.0008,1.0)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"

    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"{zoom},fps={FPS}"
    )

    command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_file),
    ]

    if has_audio:
        command += ["-i", str(audio_file)]

    command += [
        "-t", str(max(3, duration)),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", VIDEO_PRESET,
        "-crf", VIDEO_CRF,
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]

    if has_audio:
        command += ["-c:a", "aac", "-b:a", "96k", "-shortest"]
    else:
        command += ["-an"]

    command.append(str(video_file))

    result = run_command(command)
    return video_file if result.returncode == 0 and video_file.exists() else None


def combine_videos(video_files, output_file):
    concat_file = output_file.parent / "script2cinema_concat.txt"
    with concat_file.open("w", encoding="utf-8") as f:
        for video in video_files:
            path = str(video).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{path}'\n")

    result = run_command([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy", "-movflags", "+faststart",
        str(output_file),
    ])
    return result.returncode == 0 and output_file.exists()


# ============================================================
# SUBTITLES + SHORTS
# ============================================================

def create_srt(scenes, total_seconds, output_file):
    if not scenes:
        return False

    duration_per_scene = total_seconds / len(scenes)

    def timestamp(seconds):
        total = int(seconds)
        ms = int((seconds - total) * 1000)
        return (
            f"{total//3600:02d}:"
            f"{(total%3600)//60:02d}:"
            f"{total%60:02d},{ms:03d}"
        )

    with open(output_file, "w", encoding="utf-8") as f:
        for i, scene in enumerate(scenes, 1):
            start = (i - 1) * duration_per_scene
            end = i * duration_per_scene
            text = clean_dialogue_text(scene["text"])[:700]
            if not text:
                text = scene["title"]

            f.write(
                f"{i}\n{timestamp(start)} --> {timestamp(end)}\n"
                f"{text}\n\n"
            )

    return True


def burn_subtitles(video_file, subtitle_file, output_file):
    subtitle_path = str(subtitle_file).replace("\\", "/").replace(":", "\\:")

    result = run_command([
        "ffmpeg", "-y",
        "-i", str(video_file),
        "-vf", f"subtitles='{subtitle_path}'",
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", VIDEO_PRESET,
        "-crf", VIDEO_CRF,
        "-movflags", "+faststart",
        str(output_file),
    ])
    return result.returncode == 0 and output_file.exists()


def create_shorts(video_file, output_directory, number_of_shorts=3):
    output_directory.mkdir(parents=True, exist_ok=True)
    shorts = []

    for i in range(number_of_shorts):
        start = i * 30
        output_file = output_directory / f"short_{i+1:02d}.mp4"

        result = run_command([
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(video_file),
            "-t", "30",
            "-vf",
            "scale=720:1280:force_original_aspect_ratio=increase,"
            "crop=720:1280",
            "-r", str(FPS),
            "-c:v", "libx264",
            "-preset", VIDEO_PRESET,
            "-crf", "30",
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            str(output_file),
        ])

        if result.returncode == 0 and output_file.exists():
            shorts.append(output_file)

    return shorts


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("🎥 Video Settings")

    video_type = st.radio(
        "Video Type",
        ["Short Video", "Long Video"],
        index=1,
    )

    if video_type == "Short Video":
        duration_option = st.selectbox(
            "Duration",
            ["15 seconds", "30 seconds", "60 seconds", "90 seconds"],
        )
        custom_minutes = None
    else:
        duration_option = st.selectbox(
            "Duration",
            ["5 minutes", "10 minutes", "15 minutes", "20 minutes", "30 minutes", "Custom"],
            index=2,
        )
        custom_minutes = None
        if duration_option == "Custom":
            custom_minutes = st.number_input(
                "Custom duration (minutes)",
                min_value=1,
                max_value=180,
                value=15,
                step=1,
            )

    aspect_ratio = st.selectbox(
        "Aspect Ratio",
        ["16:9 — YouTube Long Video", "9:16 — Shorts / Reels / TikTok", "1:1 — Square"],
    )

    st.divider()
    st.header("🎙️ Audio")

    voice_style = st.selectbox(
        "Voice Style",
        ["Natural", "Cinematic", "Dramatic", "Calm", "Energetic"],
    )

    voice_name = st.selectbox(
        "Voice",
        [
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-GB-SoniaNeural",
            "en-IN-NeerjaNeural",
            "en-IN-PrabhatNeural",
        ],
    )

    emotion_mode = st.selectbox(
        "Emotion",
        ["Automatic", "Neutral", "Happy", "Sad", "Angry", "Fear", "Excited", "Serious"],
    )

    music_mode = st.selectbox(
        "Background Music",
        ["Automatic", "Cinematic", "Emotional", "Suspense", "Action", "Calm", "None"],
    )

    subtitles = st.checkbox("Generate subtitles", value=True)
    auto_shorts = st.checkbox("Create Shorts from final video", value=False)

    st.divider()
    st.caption("Zero-API mode • Local cinematic artwork • No app-added watermark")


# ============================================================
# HEADER + SCRIPT
# ============================================================

st.markdown(
    """
    <div style="
        padding:1.3rem 1.5rem;
        border-radius:18px;
        border:1px solid rgba(128,128,128,.25);
        margin-bottom:1rem;
    ">
        <h1 style="margin:0;">🎬 Script2Cinema AI</h1>
        <p style="margin:.5rem 0 0;">
            Turn one script into long-form video + optional Shorts.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("📝 Your Script")

script = st.text_area(
    "Complete script",
    height=450,
    placeholder="""SCENE 1 — THE SKY

The ancient mountain kingdom sleeps beneath a storm.

Mother: Get inside!

Child: Mama... the sky is breaking?

SCENE 2 — THE VILLAGE

Aarav cuts wood while Bir eats beside him.

Aarav: Did you hear that?

Bir: I heard nothing. And I would like to keep it that way.""",
    label_visibility="collapsed",
)

st.caption(
    "Tip: use headings such as SCENE 1 — THE SKY and "
    "speaker lines such as Aarav: dialogue for the most accurate detection."
)

col1, col2 = st.columns(2)

with col1:
    analyze = st.button("🔍 Analyze Script", use_container_width=True)

with col2:
    generate = st.button(
        "🎬 Create Video",
        use_container_width=True,
        type="primary",
    )


# ============================================================
# ANALYSIS + GENERATION
# ============================================================

if analyze or generate:
    if not script.strip():
        st.warning("Pehle apni script paste karein.")
        st.stop()

    scenes = detect_scenes(script)
    characters = detect_characters(script)
    dialogues = count_dialogues(script)
    estimated = estimate_duration(script)

    st.divider()
    st.subheader("🔎 Script Analysis")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scenes", len(scenes))
    c2.metric("Characters", len(characters))
    c3.metric("Dialogue Lines", dialogues)
    c4.metric("Estimated Voice Time", f"{estimated:.1f} min")

    if characters:
        st.subheader("👥 Characters Detected")
        cols = st.columns(min(max(len(characters), 1), 4))
        for i, character in enumerate(characters):
            cols[i % len(cols)].write(f"**{character}**")

    st.subheader("🎞️ Scene Breakdown")
    for scene in scenes:
        with st.expander(
            f"Scene {scene['number']} — {scene['title']}",
            expanded=False,
        ):
            st.write(scene["text"])
            st.caption("🎥 Visual prompt: " + scene_visual_prompt(scene))

    if generate:
        if not ffmpeg_available():
            st.error(
                "FFmpeg is missing. Add a file named packages.txt to your GitHub "
                "repository with the single line: ffmpeg"
            )
            st.stop()

        if duration_option == "Custom":
            target_seconds = max(60, int(custom_minutes * 60))
        else:
            m = re.search(r"(\d+)", duration_option)
            target_seconds = int(m.group(1)) * (60 if "minute" in duration_option else 1)

        scene_duration = max(3, target_seconds / max(1, len(scenes)))

        st.divider()
        st.subheader("🎬 Video Production")
        st.info(
            f"**Mode:** {video_type}  |  "
            f"**Target:** {duration_option}  |  "
            f"**Scenes:** {len(scenes)}  |  "
            f"**Aspect:** {aspect_ratio}  |  "
            f"**Voice:** {voice_style}  |  "
            f"**Emotion:** {emotion_mode}  |  "
            f"**Music:** {music_mode}"
        )

        progress = st.progress(0, text="Preparing production...")

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            scene_videos = []

            for i, scene in enumerate(scenes):
                progress.progress(
                    int((i / max(1, len(scenes))) * 82),
                    text=f"Rendering cinematic scene {i+1}/{len(scenes)}...",
                )

                rendered = render_scene(
                    scene,
                    scene_duration,
                    tmp,
                    voice_name,
                )
                if rendered:
                    scene_videos.append(rendered)

            if not scene_videos:
                st.error("No scene video could be rendered.")
                st.stop()

            final_file = OUTPUT_DIR / "script2cinema_final.mp4"
            progress.progress(86, text="Combining scenes...")

            if not combine_videos(scene_videos, final_file):
                st.error("Final MP4 assembly failed.")
                st.stop()

            if subtitles:
                progress.progress(92, text="Burning subtitles...")
                srt_file = tmp / "subtitles.srt"
                subtitle_video = OUTPUT_DIR / "script2cinema_final_subtitles.mp4"

                create_srt(scenes, target_seconds, srt_file)

                if burn_subtitles(final_file, srt_file, subtitle_video):
                    final_file = subtitle_video

            progress.progress(100, text="Production complete.")
            st.success("🎉 Video ready.")

            st.video(str(final_file))

            with open(final_file, "rb") as f:
                st.download_button(
                    "⬇️ Download Final MP4",
                    data=f,
                    file_name="script2cinema_final.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                )

            if auto_shorts:
                st.divider()
                st.subheader("📱 Automatic Shorts")

                shorts = create_shorts(
                    final_file,
                    OUTPUT_DIR / "shorts",
                    number_of_shorts=3,
                )

                if shorts:
                    st.success(f"{len(shorts)} Shorts created.")

                    for i, short_file in enumerate(shorts, 1):
                        with st.expander(f"Short {i}"):
                            st.video(str(short_file))
                            with open(short_file, "rb") as f:
                                st.download_button(
                                    f"⬇️ Download Short {i}",
                                    data=f,
                                    file_name=f"script2cinema_short_{i}.mp4",
                                    mime="video/mp4",
                                    key=f"short_download_{i}",
                                    use_container_width=True,
                                )
                else:
                    st.info("Shorts could not be extracted.")


st.divider()
st.caption(
    "Script2Cinema AI • Long-form + Shorts • "
    "Zero-API cinematic mode • No app-added watermark"
)
