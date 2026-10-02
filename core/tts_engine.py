import asyncio
from pathlib import Path


VOICE_RATES = {
    "Natural": "+0%",
    "Cinematic": "-8%",
    "Dramatic": "-12%",
    "Calm": "-15%",
    "Energetic": "+8%",
}


def generate_voice(
    text: str,
    output_file,
    voice: str,
    style: str = "Natural",
):
    try:
        import edge_tts

        output_file = Path(output_file)

        rate = VOICE_RATES.get(
            style,
            "+0%",
        )

        async def create():
            communicator = edge_tts.Communicate(
                text,
                voice,
                rate=rate,
            )

            await communicator.save(
                str(output_file)
            )

        asyncio.run(create())

        return (
            output_file.exists()
            and output_file.stat().st_size > 0
        )

    except Exception:
        return False
