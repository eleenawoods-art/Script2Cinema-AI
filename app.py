```python
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import streamlit as st


# ============================================================
# APP CONFIG
# ============================================================

st.set_page_config(
    page_title="Script2Cinema AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_DIR = Path(__file__).parent
OUTPUT_DIR = APP_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# SCRIPT ANALYSIS
# ============================================================

def detect_scenes(script: str):
    """Detect scene headings or split a long script into blocks."""

    if not script.strip():
        return []

    heading_pattern = re.compile(
        r"(?im)^(scene\s+\d+|int\.|ext\.|chapter\s+\d+|سین\s*\d+).*$"
    )

    matches = list(heading_pattern.finditer(script))

    if matches:
        scenes = []

        for i, match in enumerate(matches):
            start = match.start()

            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(script)

            scenes.append(
                {
                    "number": i + 1,
                    "title": match.group(0).strip(),
                    "text": script[start:end].strip(),
                }
            )

        return scenes

    # Fallback for scripts without scene headings.
    blocks = [
        block.strip()
        for block in re.split(r"\n\s*\n\s*\n+", script)
        if block.strip()
    ]

    if not blocks:
        blocks = [script.strip()]

    return [
        {
            "number": i + 1,
            "title": f"Scene {i + 1}",
            "text": block,
        }
        for i, block in enumerate(blocks)
    ]


def detect_characters(script: str):
    """Detect Character: dialogue and Character - dialogue."""

    characters = []

    patterns = [
        r"(?m)^\s*([A-Za-z][A-Za-z0-9 _'-]{1,40})\s*:\s+",
        r"(?m)^\s*([A-Za-z][A-Za-z0-9 _'-]{1,40})\s*-\s+",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, script):
            name = match.group(1).strip()

            if name and name not in characters:
                characters.append(name)

    return characters


def count_dialogues(script: str):
    pattern = (
        r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{1,40}"
        r"\s*:\s+.+$"
    )

    return len(re.findall(pattern, script))


def estimate_duration(script: str):
    """Approximate narration duration."""

    words = len(re.findall(r"\b[\w'-]+\b", script))

    if not words:
        return 0

    return words / 130


def clean_dialogue_text(text: str):
    """Remove scene headings and simple speaker labels."""

    text = re.sub(
        r"(?im)^\s*"
        r"(scene\s+\d+|int\.|ext\.|chapter\s+\d+|سین\s*\d+)"
        r".*$",
        "",
        text,
    )

    text = re.sub(
        r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{1,40}\s*:\s*",
        "",
        text,
    )

    text = re.sub(
        r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{1,40}\s*-\s*",
        "",
        text,
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# SYSTEM CHECKS
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
# TTS
# ============================================================

def generate_voice(text, output_file, voice):
    """
    Optional Edge TTS narration.

    If Edge TTS is unavailable, the video can still be rendered
    without narration.
    """

    try:
        import asyncio
        import edge_tts

        async def create_audio():
            communicate = edge_tts.Communicate(
                text,
                voice,
            )

            await communicate.save(str(output_file))

        asyncio.run(create_audio())

        return (
            output_file.exists()
            and output_file.stat().st_size > 0
        )

    except Exception:
        return False


# ============================================================
# CINEMATIC SCENE VISUAL
# ============================================================

def create_scene_visual(
    title,
    text,
    output_file,
    width=1280,
    height=720,
):
    """
    Creates a clean cinematic scene visual using Pillow.

    No app-added watermark is placed on the video.
    """

    from PIL import Image, ImageDraw, ImageFont

    image = Image.new(
        "RGB",
        (width, height),
        (10, 12, 20),
    )

    draw = ImageDraw.Draw(image)

    # Cinematic gradient.
    for y in range(height):
        value = int(15 + 35 * (y / height))

        draw.line(
            (0, y, width, y),
            fill=(
                value // 2,
                value // 2,
                value,
            ),
        )

    try:
        title_font = ImageFont.truetype(
            "DejaVuSans-Bold.ttf",
            52,
        )

        body_font = ImageFont.truetype(
            "DejaVuSans.ttf",
            34,
        )

        small_font = ImageFont.truetype(
            "DejaVuSans.ttf",
            22,
        )

    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Frame.
    draw.rectangle(
        (
            70,
            70,
            width - 70,
            height - 70,
        ),
        outline=(220, 220, 220),
        width=2,
    )

    draw.text(
        (105, 105),
        title[:70],
        font=title_font,
        fill=(245, 245, 245),
    )

    # Wrap body.
    words = text.split()

    lines = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()

        if len(candidate) > 58:
            lines.append(current)
            current = word
        else:
            current = candidate

    if current:
        lines.append(current)

    y = 220

    for line in lines[:9]:
        draw.text(
            (105, y),
            line,
            font=body_font,
            fill=(225, 225, 225),
        )

        y += 48

    # Small product label.
    draw.text(
        (105, height - 115),
        "SCRIPT2CINEMA",
        font=small_font,
        fill=(155, 155, 155),
    )

    image.save(output_file)


# ============================================================
# SCENE VIDEO
# ============================================================

def render_scene(
    scene,
    duration,
    temp_directory,
    voice_name,
):
    scene_number = scene["number"]

    image_file = (
        Path(temp_directory)
        / f"scene_{scene_number:03d}.png"
    )

    video_file = (
        Path(temp_directory)
        / f"scene_{scene_number:03d}.mp4"
    )

    audio_file = (
        Path(temp_directory)
        / f"scene_{scene_number:03d}.mp3"
    )

    dialogue = clean_dialogue_text(
        scene["text"]
    )

    create_scene_visual(
        scene["title"],
        dialogue or "Cinematic scene",
        image_file,
    )

    has_audio = False

    if dialogue:
        has_audio = generate_voice(
            dialogue[:12000],
            audio_file,
            voice_name,
        )

    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_file),
    ]

    if has_audio:
        command.extend(
            [
                "-i",
                str(audio_file),
            ]
        )

    command.extend(
        [
            "-t",
            str(max(3, duration)),
            "-vf",
            (
                "scale=1280:720:"
                "force_original_aspect_ratio=decrease,"
                "pad=1280:720:"
                "(ow-iw)/2:"
                "(oh-ih)/2"
            ),
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]
    )

    if has_audio:
        command.extend(
            [
                "-c:a",
                "aac",
                "-shortest",
            ]
        )
    else:
        command.append("-an")

    command.append(str(video_file))

    result = run_command(command)

    if (
        result.returncode == 0
        and video_file.exists()
    ):
        return video_file

    return None


# ============================================================
# VIDEO CONCATENATION
# ============================================================

def combine_videos(video_files, output_file):
    concat_file = (
        output_file.parent
        / "script2cinema_concat.txt"
    )

    with concat_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        for video in video_files:

            safe_path = (
                str(video)
                .replace("\\", "/")
                .replace("'", "'\\''")
            )

            file.write(
                f"file '{safe_path}'\n"
            )

    result = run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_file),
        ]
    )

    return (
        result.returncode == 0
        and output_file.exists()
    )


# ============================================================
# SUBTITLES
# ============================================================

def create_srt(
    scenes,
    total_seconds,
    output_file,
):
    if not scenes:
        return False

    duration_per_scene = (
        total_seconds / len(scenes)
    )

    def timestamp(seconds):

        total = int(seconds)

        milliseconds = int(
            (seconds - total) * 1000
        )

        hours = total // 3600

        minutes = (
            total % 3600
        ) // 60

        seconds_only = total % 60

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds_only:02d},"
            f"{milliseconds:03d}"
        )

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as file:

        for index, scene in enumerate(
            scenes,
            start=1,
        ):

            start = (
                index - 1
            ) * duration_per_scene

            end = (
                index
            ) * duration_per_scene

            text = clean_dialogue_text(
                scene["text"]
            )[:500]

            file.write(
                f"{index}\n"
                f"{timestamp(start)} --> "
                f"{timestamp(end)}\n"
                f"{text}\n\n"
            )

    return True


def burn_subtitles(
    video_file,
    subtitle_file,
    output_file,
):
    subtitle_path = (
        str(subtitle_file)
        .replace("\\", "/")
        .replace(":", "\\:")
    )

    result = run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_file),
            "-vf",
            f"subtitles='{subtitle_path}'",
            "-c:a",
            "copy",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-movflags",
            "+faststart",
            str(output_file),
        ]
    )

    return (
        result.returncode == 0
        and output_file.exists()
    )


# ============================================================
# SHORTS
# ============================================================

def create_shorts(
    video_file,
    output_directory,
    number_of_shorts=3,
):
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    shorts = []

    for index in range(
        number_of_shorts
    ):

        start_time = index * 30

        output_file = (
            output_directory
            / f"short_{index + 1:02d}.mp4"
        )

        result = run_command(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(start_time),
                "-i",
                str(video_file),
                "-t",
                "30",
                "-vf",
                (
                    "scale=720:1280:"
                    "force_original_aspect_ratio=decrease,"
                    "pad=720:1280:"
                    "(ow-iw)/2:"
                    "(oh-ih)/2"
                ),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(output_file),
            ]
        )

        if (
            result.returncode == 0
            and output_file.exists()
        ):
            shorts.append(output_file)

    return shorts


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("🎥 Video Settings")

    video_type = st.radio(
        "Video Type",
        [
            "Short Video",
            "Long Video",
        ],
        index=1,
    )

    if video_type == "Short Video":

        duration_option = st.selectbox(
            "Duration",
            [
                "15 seconds",
                "30 seconds",
                "60 seconds",
                "90 seconds",
            ],
        )

        custom_minutes = None

    else:

        duration_option = st.selectbox(
            "Duration",
            [
                "5 minutes",
                "10 minutes",
                "15 minutes",
                "20 minutes",
                "30 minutes",
                "Custom",
            ],
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
        [
            "16:9 — YouTube Long Video",
            "9:16 — Shorts / Reels / TikTok",
            "1:1 — Square",
        ],
    )

    st.divider()

    st.header("🎙️ Audio")

    voice_style = st.selectbox(
        "Voice Style",
        [
            "Natural",
            "Cinematic",
            "Dramatic",
            "Calm",
            "Energetic",
        ],
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
        [
            "Automatic",
            "Neutral",
            "Happy",
            "Sad",
            "Angry",
            "Fear",
            "Excited",
            "Serious",
        ],
    )

    music_mode = st.selectbox(
        "Background Music",
        [
            "Automatic",
            "Cinematic",
            "Emotional",
            "Suspense",
            "Action",
            "Calm",
            "None",
        ],
    )

    subtitles = st.checkbox(
        "Generate subtitles",
        value=True,
    )

    auto_shorts = st.checkbox(
        "Create Shorts from final video",
        value=True,
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div style="
        padding:1.3rem 1.5rem;
        border-radius:18px;
        border:1px solid rgba(128,128,128,.25);
        margin-bottom:1rem;
    ">
        <h1 style="margin:0;">
            🎬 Script2Cinema AI
        </h1>

        <p style="margin:.5rem 0 0;">
            Long-form + Shorts production
            from one script.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SCRIPT
# ============================================================

st.subheader("📝 Your Script")

script = st.text_area(
    "Complete script",
    height=450,
    placeholder="""Scene 1

Ali enters the room.

Ali: Tum yahan kaise aaye?

Sara: Mujhe tumse zaroori baat karni hai.

Scene 2

Ali looks at Sara.

Ali: Kaisi baat?

Sara: Woh raaz jo tum das saal se chhupa rahe ho...""",
    label_visibility="collapsed",
)

st.caption(
    "Long scripts supported. "
    "Use Scene headings and Character: dialogue "
    "for cleaner detection."
)


# ============================================================
# BUTTONS
# ============================================================

column_one, column_two = st.columns(2)

with column_one:

    analyze = st.button(
        "🔍 Analyze Script",
        use_container_width=True,
    )

with column_two:

    generate = st.button(
        "🎬 Create Video",
        use_container_width=True,
        type="primary",
    )


# ============================================================
# ANALYSIS
# ============================================================

if analyze or generate:

    if not script.strip():

        st.warning(
            "Pehle apni script paste karein."
        )

        st.stop()

    scenes = detect_scenes(script)

    characters = detect_characters(script)

    dialogues = count_dialogues(script)

    estimated = estimate_duration(script)

    st.divider()

    st.subheader(
        "🔎 Script Analysis"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Scenes",
        len(scenes),
    )

    c2.metric(
        "Characters",
        len(characters),
    )

    c3.metric(
        "Dialogue Lines",
        dialogues,
    )

    c4.metric(
        "Estimated Voice Time",
        f"{estimated:.1f} min",
    )

    # --------------------------------------------------------
    # CHARACTERS
    # --------------------------------------------------------

    if characters:

        st.subheader(
            "👥 Characters Detected"
        )

        character_columns = st.columns(
            min(
                max(len(characters), 1),
                4,
            )
        )

        for index, character in enumerate(
            characters
        ):

            character_columns[
                index % len(character_columns)
            ].write(
                f"**{character}**"
            )

    # --------------------------------------------------------
    # SCENES
    # --------------------------------------------------------

    st.subheader(
        "🎞️ Scene Breakdown"
    )

    for scene in scenes:

        with st.expander(
            f"Scene {scene['number']} — "
            f"{scene['title']}",
            expanded=False,
        ):

            st.write(
                scene["text"]
            )

            scene_columns = st.columns(4)

            scene_columns[0].write(
                "🎙️ Voice"
            )

            scene_columns[1].write(
                "😊 Emotion"
            )

            scene_columns[2].write(
                "🎵 Music"
            )

            scene_columns[3].write(
                "🎥 Visual"
            )


# ============================================================
# GENERATION
# ============================================================

    if generate:

        st.divider()

        if not ffmpeg_available():

            st.error(
                "FFmpeg is not installed "
                "or is not available in PATH."
            )

            st.info(
                "Install FFmpeg on the computer/server "
                "before using actual MP4 rendering."
            )

            st.stop()

        # Determine target duration.
        if duration_option == "Custom":

            target_seconds = max(
                60,
                int(custom_minutes * 60),
            )

        else:

            match = re.search(
                r"(\d+)",
                duration_option,
            )

            target_seconds = (
                int(match.group(1))
                if match
                else 60
            )

        scene_duration = max(
            3,
            target_seconds
            / max(1, len(scenes)),
        )

        st.subheader(
            "🎬 Video Production"
        )

        st.info(
            f"""
            **Mode:** {video_type}

            **Target:** {duration_option}

            **Aspect Ratio:** {aspect_ratio}

            **Scenes:** {len(scenes)}

            **Voice:** {voice_style}

            **Emotion:** {emotion_mode}

            **Music:** {music_mode}

            **Subtitles:** {"On" if subtitles else "Off"}
            """
        )

        progress = st.progress(
            0,
            text="Preparing production...",
        )

        with tempfile.TemporaryDirectory() as temp_directory:

            temp_directory = Path(
                temp_directory
            )

            scene_videos = []

            for index, scene in enumerate(
                scenes
            ):

                progress.progress(
                    int(
                        (
                            index
                            / max(
                                1,
                                len(scenes),
                            )
                        )
                        * 80
                    ),
                    text=(
                        f"Rendering scene "
                        f"{index + 1}/"
                        f"{len(scenes)}..."
                    ),
                )

                rendered = render_scene(
                    scene=scene,
                    duration=scene_duration,
                    temp_directory=temp_directory,
                    voice_name=voice_name,
                )

                if rendered:
                    scene_videos.append(
                        rendered
                    )

            if not scene_videos:

                progress.empty()

                st.error(
                    "No scene video could "
                    "be rendered."
                )

                st.stop()

            final_file = (
                OUTPUT_DIR
                / "script2cinema_final.mp4"
            )

            progress.progress(
                85,
                text="Combining scenes...",
            )

            combined = combine_videos(
                scene_videos,
                final_file,
            )

            if not combined:

                progress.empty()

                st.error(
                    "Final MP4 assembly failed."
                )

                st.stop()

            # ------------------------------------------------
            # SUBTITLES
            # ------------------------------------------------

            if subtitles:

                subtitle_file = (
                    temp_directory
                    / "subtitles.srt"
                )

                subtitle_video = (
                    OUTPUT_DIR
                    / "script2cinema_final_subtitles.mp4"
                )

                create_srt(
                    scenes,
                    target_seconds,
                    subtitle_file,
                )

                burned = burn_subtitles(
                    final_file,
                    subtitle_file,
                    subtitle_video,
                )

                if burned:
                    final_file = subtitle_video

            progress.progress(
                100,
                text="Production complete.",
            )

            st.success(
                "🎉 Video ready."
            )

            video_data = final_file.read_bytes()

            st.video(
                video_data
            )

            st.download_button(
                "⬇️ Download Final MP4",
                data=video_data,
                file_name="script2cinema_final.mp4",
                mime="video/mp4",
                use_container_width=True,
            )

            # ------------------------------------------------
            # AUTOMATIC SHORTS
            # ------------------------------------------------

            if auto_shorts:

                st.divider()

                st.subheader(
                    "📱 Automatic Shorts"
                )

                shorts_directory = (
                    OUTPUT_DIR
                    / "shorts"
                )

                shorts = create_shorts(
                    final_file,
                    shorts_directory,
                    number_of_shorts=3,
                )

                if shorts:

                    st.success(
                        f"{len(shorts)} Shorts created."
                    )

                    for index, short_file in enumerate(
                        shorts,
                        start=1,
                    ):

                        with st.expander(
                            f"Short {index}"
                        ):

                            short_data = (
                                short_file.read_bytes()
                            )

                            st.video(
                                short_data
                            )

                            st.download_button(
                                f"⬇️ Download Short {index}",
                                data=short_data,
                                file_name=(
                                    f"script2cinema_short_"
                                    f"{index}.mp4"
                                ),
                                mime="video/mp4",
                                key=(
                                    f"short_download_"
                                    f"{index}"
                                ),
                                use_container_width=True,
                            )

                else:

                    st.info(
                        "Shorts could not be extracted."
                    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Script2Cinema AI • "
    "Long-form + Shorts • "
    "No app-added watermark"
)
```
