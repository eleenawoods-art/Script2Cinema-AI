import re
import streamlit as st

st.set_page_config(
    page_title="Script2Cinema AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Helpers
# -----------------------------

def detect_scenes(script: str):
    """Basic scene detection from common scene headings or blank-line blocks."""
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
            end = matches[i + 1].start() if i + 1 < len(matches) else len(script)
            block = script[start:end].strip()

            scenes.append({
                "number": i + 1,
                "title": match.group(0).strip(),
                "text": block,
            })
        return scenes

    # Fallback: split by multiple blank lines
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
    """Detect dialogue names such as Ali: Hello or ALI - Hello."""
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
    pattern = r"(?m)^\s*[A-Za-z][A-Za-z0-9 _'-]{1,40}\s*:\s+.+$"
    return len(re.findall(pattern, script))


def estimate_duration(script: str):
    """
    Rough narration estimate.
    Around 130 words/minute is used only for planning.
    Actual duration will depend on generated voice speed and scene timing.
    """
    words = len(re.findall(r"\b[\w'-]+\b", script))
    minutes = words / 130 if words else 0
    return minutes


# -----------------------------
# Header
# -----------------------------

st.markdown(
    """
    <div style="
        padding: 1.2rem 1.4rem;
        border-radius: 18px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 1rem;
    ">
        <h1 style="margin:0;">🎬 Script2Cinema AI</h1>
        <p style="margin:.45rem 0 0 0;">
            Script ko scenes, dialogue, voice, emotion, music aur video workflow mein convert karein.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Sidebar
# -----------------------------

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
                "Custom duration (minutes)",
                min_value=1,
                max_value=180,
                value=15,
                step=1,
            )
        else:
            custom_minutes = None

    aspect_ratio = st.selectbox(
        "Aspect Ratio",
        ["16:9 — YouTube Long Video", "9:16 — Shorts / Reels / TikTok", "1:1 — Square"],
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

    subtitles = st.checkbox("Generate subtitles", value=True)

# -----------------------------
# Main Script Area
# -----------------------------

st.subheader("📝 Your Script")

script = st.text_area(
    "Complete script yahan paste karein",
    height=420,
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
    "Long scripts allowed hain. App script ko scenes aur dialogues mein analyze karegi."
)

# -----------------------------
# Analyze
# -----------------------------

col1, col2 = st.columns([1, 1])

with col1:
    analyze = st.button(
        "🔍 Analyze Script",
        use_container_width=True,
        type="secondary",
    )

with col2:
    generate = st.button(
        "🎬 Create Video",
        use_container_width=True,
        type="primary",
    )

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

    # -----------------------------
    # Validation
    # -----------------------------

    st.subheader("✅ Pre-Production Check")

    checks = [
        ("Script detected", True),
        ("Scene structure detected", len(scenes) > 0),
        ("Dialogue structure checked", dialogues >= 0),
        ("Voice settings selected", bool(voice_style)),
        ("Emotion mode selected", bool(emotion_mode)),
        ("Music setting selected", bool(music_mode)),
    ]

    all_ok = True

    for label, status in checks:
        if status:
            st.success(f"✓ {label}")
        else:
            all_ok = False
            st.error(f"✗ {label}")

    # -----------------------------
    # Characters
    # -----------------------------

    if characters:
        st.subheader("👥 Characters Detected")

        character_cols = st.columns(min(len(characters), 4))

        for index, character in enumerate(characters):
            character_cols[index % len(character_cols)].write(
                f"**{character}**"
            )
    else:
        st.info(
            "Character names automatically detect nahi huay. "
            "Dialogue format `Character: dialogue` use karna best rahega."
        )

    # -----------------------------
    # Scenes
    # -----------------------------

    st.subheader("🎞️ Scene Breakdown")

    for scene in scenes:
        with st.expander(
            f"Scene {scene['number']} — {scene['title']}",
            expanded=False,
        ):
            st.write(scene["text"])

            scene_cols = st.columns(4)

            scene_cols[0].write("🎙️ Voice")
            scene_cols[1].write("😊 Emotion")
            scene_cols[2].write("🎵 Music")
            scene_cols[3].write("🎥 Visual")

    # -----------------------------
    # Generation Status
    # -----------------------------

    if generate:
        st.divider()

        if not all_ok:
            st.error(
                "Kuch pre-production checks complete nahi huay. "
                "Pehle unhein fix karein."
            )
            st.stop()

        st.subheader("🎬 Video Production Plan")

        if video_type == "Short Video":
            selected_duration = duration_option
        elif duration_option == "Custom":
            selected_duration = f"{custom_minutes} minutes"
        else:
            selected_duration = duration_option

        st.info(
            f"""
            **Mode:** {video_type}

            **Target Duration:** {selected_duration}

            **Format:** {aspect_ratio}

            **Voice:** {voice_style}

            **Emotion:** {emotion_mode}

            **Music:** {music_mode}

            **Subtitles:** {"Yes" if subtitles else "No"}
            """
        )

        st.progress(0.15, text="Scene planning ready")

        st.warning(
            "Foundation ready hai. Actual AI voice, visual generation aur "
            "MP4 rendering engines next modules mein connect honge."
        )

        st.caption(
            "Is version mein app koi watermark add nahi karti."
        )

# -----------------------------
# Footer
# -----------------------------

st.divider()

st.caption(
    "Script2Cinema AI • Shorts + Long-form video workflow • No app-added watermark"
)
