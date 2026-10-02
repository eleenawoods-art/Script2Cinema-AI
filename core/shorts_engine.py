from pathlib import Path

from .video_engine import run_command


def create_shorts(
    video_file,
    output_directory,
    number_of_shorts=3,
    duration=30,
):
    output_directory = Path(
        output_directory
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    shorts = []

    for index in range(
        number_of_shorts
    ):

        start = (
            index * duration
        )

        output_file = (
            output_directory
            / f"short_{index + 1:02d}.mp4"
        )

        result = run_command(
            [
                "ffmpeg",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(video_file),
                "-t",
                str(duration),
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
                str(output_file),
            ]
        )

        if (
            result.returncode == 0
            and output_file.exists()
            and output_file.stat().st_size > 0
        ):
            shorts.append(
                output_file
            )

    return shorts
