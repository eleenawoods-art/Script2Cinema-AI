import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import streamlit as st


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Script2Cinema AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# SCRIPT FUNCTIONS
# ============================================================

def detect_scenes(script):
    if not script.strip():
        return []

    pattern = re.compile(
        r"(?im)^(scene\s+\d+|int\.|ext\.|chapter\s+\d+|سین\s*\d+).*$"
    )

    matches = list(pattern.finditer(script))

    if matches:
        scenes = []

        for i, match in enumerate(matches):
            start = match.start()
            end = (
                matches[i + 1].start()
                if i + 1 < len(matches)
                else len(script)
            )

            scenes.append(
                {
                    "number": i + 1,
                    "title": match.group(0).strip(),
                    "text": script[start:end].strip(),
                }
            )

        return scenes

    blocks = [
        x.strip()
        for x in re.split(r"\n\s*\n\s*\n+", script)
        if x.strip()
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


def detect_characters(script):
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


def count_dialogues(script):
    pattern = (
        r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{1,40}"
        r"\s*:\s+.+$"
    )

    return len(re.findall(pattern, script))


def estimate_duration(script):
    words = len(
        re.findall(
            r"\b[\w'-]+\b",
            script,
        )
    )

    return words / 130 if words else 0


def clean_scene_text(text):
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

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================
# FFMPEG
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
    try:
        import asyncio
        import edge_tts

        async def create_audio():
            communicator = edge_tts.Communicate(
                text,
                voice,
            )
            await communicator.save(
                str(output_file)
            )

        asyncio.run(create_audio())

        return (
            output_file.exists()
            and output_file.stat().st_size > 0
        )

    except Exception:
        return False


# ============================================================
# SCENE IMAGE
# ============================================================

def create_scene_image(
    title,
    text,
    output_file,
    width=1280,
    height=720,
):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new(
        "RGB",
        (width, height),
        (12, 14, 24),
    )

    draw = ImageDraw.Draw(image)

    # Background only.
    # No watermark or branding is added.
    for y in range(height):
        ratio = y / height

        r = int(12 + 18 * ratio)
        g = int(14 + 20 * ratio)
        b = int(24 + 38 * ratio)

        draw.line(
            (0, y, width, y),
            fill=(r, g, b),
        )

    try:
        title_font = ImageFont.truetype(
            "DejaVuSans-Bold.ttf",
            48,
        )

        body_font = ImageFont.truetype(
            "DejaVuSans.ttf",
            30,
        )

    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    draw.rectangle(
        (
            60,
            60,
            width - 60,
            height - 60,
        ),
        outline=(160, 165, 180),
        width=2,
    )

    draw.text(
        (100, 100),
        title[:80],
        font=title_font,
        fill=(245, 245, 245),
    )

    words = text.split()

    lines = []
    current = ""

    for word in words:
        candidate = (
            f"{current} {word}".strip()
        )

        if len(candidate) > 58:
            if current:
                lines.append(current)

            current = word
        else:
            current = candidate

    if current:
        lines.append(current)

    y = 205

    for line in lines[:10]:
        draw.text(
            (100, y),
            line,
            font=body_font,
            fill=(225, 225, 230),
        )

        y += 46

    image.save(
        output_file,
        format="PNG",
    )


# ============================================================
# SCENE VIDEO
# ============================================================

def render_scene(
    scene,
    duration,
    temp_dir,
    voice,
):
    number = scene["number"]

    image_file = (
        temp_dir
        / f"scene_{number:03d}.png"
    )

    audio_file = (
        temp_dir
        / f"scene_{number:03d}.mp3"
    )

    video_file = (
        temp_dir
        / f"scene_{number:03d}.mp4"
    )

    text = clean_scene_text(
        scene["text"]
    )

    create_scene_image(
        scene["title"],
        text or " ",
        image_file,
    )

    audio_created = False

    if text:
        audio_created = generate_voice(
            text[:12000],
            audio_file,
            voice,
        )

    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_file),
    ]

    if audio_created:
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
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]
    )

    if audio_created:
        command.extend(
            [
                "-c:a",
                "aac",
                "-af",
                "apad",
            ]
        )
    else:
        command.append("-an")

    command.append(
        str(video_file)
    )

    result = run_command(command)

    if (
        result.returncode == 0
        and video_file.exists()
    ):
        return video_file

    return None


# ============================================================
# COMBINE
# ============================================================

def combine_videos(video_files, output_file):
    concat_file = (
        output_file.parent
        / "concat.txt"
    )

    with concat_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        for video in video_files:
            path = (
                Path(video)
                .resolve()
                .as_posix()
            )

            file.write(
                f"file '{path}'\n"
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

def make_srt(
    scenes,
    total_seconds,
    output_file,
):
    if not scenes:
        return False

    per_scene = (
        total_seconds / len(scenes)
    )

    def stamp(seconds):
        total_ms = int(
            seconds * 1000
        )

        hours = total_ms // 3600000

        minutes = (
            total_ms % 3600000
        ) // 60000

        seconds_only = (
            total_ms % 60000
        ) // 1000

        milliseconds = (
            total_ms % 1000
        )

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

        for i, scene in enumerate(
            scenes,
            start=1,
        ):
            start = (
                (i - 1)
                * per_scene
            )

            end = (
                i
                * per_scene
            )

            text = scene["text"].strip()

            file.write(
                f"{i}\n"
                f"{stamp(start)} --> "
                f"{stamp(end)}\n"
                f"{text[:600]}\n\n"
            )

    return True


def burn_subtitles(
    video,
    subtitle,
    output,
):
    subtitle_path = (
        Path(subtitle)
        .resolve()
        .as_posix()
        .replace(":", "\\:")
    )

    result = run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"subtitles='{subtitle_path}'",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )

    return (
        result.returncode == 0
        and output.exists()
    )


# ============================================================
# SHORTS
# ============================================================

def create_shorts(
    video,
    output_dir,
    count=3,
):
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    for i in range(count):
        start = i * 30

        output = (
            output_dir
            / f"short_{i + 1}.mp4"
        )

        result = run_command(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(video),
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
                "-preset",
                "medium",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )

        if (
            result.returncode == 0
            and output.exists()
            and output.stat().st_size > 0
        ):
            results.append(output)

    return results


# ============================================================
# HEADER
# ============================================================

st.title("🎬 Script2Cinema AI")

st.write(
    "Turn your script into long-form videos "
    "and Shorts."
)


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

        if duration_option == "Custom":
            custom_minutes = st.number_input(
                "Custom duration",
                min_value=1,
                max_value=180,
                value=15,
                step=1,
            )
        else:
            custom_minutes = None

    aspect_ratio = st.selectbox(
        "Aspect Ratio",
        [
            "16:9 — YouTube",
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

    voice = st.selectbox(
        "Voice",
        [
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-GB-SoniaNeural",
            "en-IN-NeerjaNeural",
            "en-IN-PrabhatNeural",
        ],
    )

    emotion = st.selectbox(
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

    music = st.selectbox(
        "Background Music",
        [
            "None",
            "Automatic",
            "Cinematic",
            "Emotional",
            "Suspense",
            "Action",
            "Calm",
        ],
    )

    subtitles = st.checkbox(
        "Generate subtitles",
        value=True,
    )

    create_shorts_option = st.checkbox(
        "Create Shorts from final video",
        value=True,
    )


# ============================================================
# SCRIPT INPUT
# ============================================================

st.subheader("📝 Your Script")

script = st.text_area(
    "Paste your complete script here",
    height=450,
    placeholder=(
        "Scene 1\n\n"
        "Ali enters the room.\n\n"
        "Ali: Tum yahan kaise aaye?\n\n"
        "Sara: Mujhe tumse zaroori baat karni hai.\n\n"
        "Scene 2\n\n"
        "Ali looks at Sara.\n\n"
        "Ali: Kaisi baat?\n\n"
        "Sara: Woh raaz jo tum das saal se chhupa rahe ho..."
    ),
)

st.caption(
    "Long scripts are supported. "
    "Scene headings and Character: dialogue "
    "format give better analysis."
)


# ============================================================
# BUTTONS
# ============================================================

col1, col2 = st.columns(2)

with col1:
    analyze = st.button(
        "🔍 Analyze Script",
        use_container_width=True,
    )

with col2:
    generate = st.button(
        "🎬 Create Video",
        use_container_width=True,
        type="primary",
    )


# ============================================================
# PROCESS
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

    st.subheader("🔎 Script Analysis")

    a, b, c, d = st.columns(4)

    a.metric(
        "Scenes",
        len(scenes),
    )

    b.metric(
        "Characters",
        len(characters),
    )

    c.metric(
        "Dialogue Lines",
        dialogues,
    )

    d.metric(
        "Estimated Voice Time",
        f"{estimated:.1f} min",
    )

    if characters:

        st.subheader(
            "👥 Characters Detected"
        )

        cols = st.columns(
            min(4, len(characters))
        )

        for i, character in enumerate(
            characters
        ):
            cols[
                i % len(cols)
            ].write(
                f"**{character}**"
            )

    st.subheader(
        "🎞️ Scene Breakdown"
    )

    for scene in scenes:

        with st.expander(
            f"Scene {scene['number']} — "
            f"{scene['title']}"
        ):
            st.write(
                scene["text"]
            )


# ============================================================
# GENERATE
# ============================================================

    if generate:

        if not ffmpeg_available():

            st.error(
                "FFmpeg is not available."
            )

            st.info(
                "Make sure packages.txt contains only: ffmpeg"
            )

            st.stop()

        if duration_option == "Custom":

            total_seconds = (
                custom_minutes * 60
            )

        else:

            number = int(
                re.search(
                    r"\d+",
                    duration_option,
                ).group()
            )

            if "second" in duration_option:
                total_seconds = number
            else:
                total_seconds = number * 60

        per_scene = max(
            3,
            total_seconds / max(
                1,
                len(scenes),
            ),
        )

        st.divider()

        st.subheader(
            "🎬 Production"
        )

        st.write(
            f"**Mode:** {video_type}"
        )

        st.write(
            f"**Target duration:** {duration_option}"
        )

        st.write(
            f"**Voice:** {voice_style}"
        )

        st.write(
            f"**Emotion:** {emotion}"
        )

        st.write(
            f"**Music:** {music}"
        )

        progress = st.progress(
            0,
            text="Preparing...",
        )

        with tempfile.TemporaryDirectory() as temp:

            temp_dir = Path(temp)

            rendered_scenes = []

            for i, scene in enumerate(
                scenes
            ):

                progress.progress(
                    int(
                        (i / max(1, len(scenes)))
                        * 80
                    ),
                    text=(
                        f"Rendering scene "
                        f"{i + 1} of "
                        f"{len(scenes)}"
                    ),
                )

                result = render_scene(
                    scene,
                    per_scene,
                    temp_dir,
                    voice,
                )

                if result:
                    rendered_scenes.append(
                        result
                    )

            if not rendered_scenes:

                st.error(
                    "No scene could be rendered."
                )

                st.stop()

            final_video = (
                OUTPUT_DIR
                / "script2cinema_final.mp4"
            )

            progress.progress(
                85,
                text="Combining scenes...",
            )

            success = combine_videos(
                rendered_scenes,
                final_video,
            )

            if not success:

                st.error(
                    "Could not create final MP4."
                )

                st.stop()

            if subtitles:

                subtitle_file = (
                    temp_dir
                    / "subtitles.srt"
                )

                subtitled_video = (
                    OUTPUT_DIR
                    / "script2cinema_subtitled.mp4"
                )

                make_srt(
                    scenes,
                    total_seconds,
                    subtitle_file,
                )

                subtitle_success = burn_subtitles(
                    final_video,
                    subtitle_file,
                    subtitled_video,
                )

                if subtitle_success:
                    final_video = subtitled_video

            progress.progress(
                100,
                text="Video complete.",
            )

            st.success(
                "🎉 Your video is ready."
            )

            video_bytes = (
                final_video.read_bytes()
            )

            st.video(
                video_bytes
            )

            st.download_button(
                "⬇️ Download MP4",
                data=video_bytes,
                file_name="script2cinema_video.mp4",
                mime="video/mp4",
                use_container_width=True,
            )

            # ------------------------------------------------
            # SHORTS
            # ------------------------------------------------

            if create_shorts_option:

                st.divider()

                st.subheader(
                    "📱 Shorts"
                )

                shorts_dir = (
                    OUTPUT_DIR
                    / "shorts"
                )

                shorts = create_shorts(
                    final_video,
                    shorts_dir,
                    count=3,
                )

                if shorts:

                    st.success(
                        f"{len(shorts)} Shorts created."
                    )

                    for i, short in enumerate(
                        shorts,
                        start=1,
                    ):

                        short_bytes = (
                            short.read_bytes()
                        )

                        with st.expander(
                            f"Short {i}"
                        ):

                            st.video(
                                short_bytes
                            )

                            st.download_button(
                                f"⬇️ Download Short {i}",
                                data=short_bytes,
                                file_name=(
                                    f"script2cinema_short_{i}.mp4"
                                ),
                                mime="video/mp4",
                                key=(
                                    f"download_short_{i}"
                                ),
                                use_container_width=True,
                            )

                else:

                    st.info(
                        "Shorts could not be created."
                    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Script2Cinema AI • "
    "Long-form + Shorts • "
    "No watermark"
)
