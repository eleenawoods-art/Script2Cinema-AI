import shutil
import subprocess
from pathlib import Path


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


def render_scene_video(
    image_file,
    output_file,
    duration,
    audio_file=None,
    width=1280,
    height=720,
):
    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_file),
    ]

    if audio_file:
        command.extend(
            [
                "-i",
                str(audio_file),
            ]
        )

    command.extend(
        [
            "-t",
            str(duration),
            "-vf",
            (
                f"scale={width}:{height}:"
                "force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:"
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

    if audio_file:
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
        str(output_file)
    )

    result = run_command(command)

    return (
        result.returncode == 0
        and Path(output_file).exists()
    )


def combine_videos(
    video_files,
    output_file,
):
    output_file = Path(output_file)

    concat_file = (
        output_file.parent
        / "concat_list.txt"
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


def create_srt(
    scenes,
    total_seconds,
    output_file,
):
    if not scenes:
        return False

    per_scene = (
        total_seconds / len(scenes)
    )

    def timestamp(seconds):
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

        for index, scene in enumerate(
            scenes,
            start=1,
        ):

            start = (
                (index - 1)
                * per_scene
            )

            end = (
                index
                * per_scene
            )

            text = scene["text"].strip()

            file.write(
                f"{index}\n"
                f"{timestamp(start)} --> "
                f"{timestamp(end)}\n"
                f"{text[:600]}\n\n"
            )

    return True


def burn_subtitles(
    video_file,
    subtitle_file,
    output_file,
):
    subtitle_path = (
        Path(subtitle_file)
        .resolve()
        .as_posix()
        .replace(":", "\\:")
        .replace("'", "\\'")
    )

    result = run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_file),
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
            str(output_file),
        ]
    )

    return (
        result.returncode == 0
        and Path(output_file).exists()
    )
