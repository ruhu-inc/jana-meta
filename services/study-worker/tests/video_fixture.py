"""A synthetic lecture clip for the W9 video tests: a few scenes of large board writing, a silent audio track or
none, encoded in memory with PyAV (installed on the gateway side, where the worker runs). Nothing here is recorded."""

from __future__ import annotations

import io
from fractions import Fraction

FPS = 2
WIDTH, HEIGHT = 640, 360


def _board(text: str, shade: tuple[int, int, int]) -> object:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (WIDTH, HEIGHT), shade)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=44)
    except TypeError:  # an older Pillow: the fixed-size default
        font = ImageFont.load_default()
    draw.text((40, 120), text, fill=(20, 20, 20), font=font)
    return image


def clip(
    scenes: list[tuple[str, int]], *, audio: bool = True, video: bool = True, container: str = "matroska"
) -> bytes:
    """`scenes` are (board text, seconds) in order; keyframes every ten seconds, a scene change at each new board."""
    import av

    buffer = io.BytesIO()
    with av.open(buffer, mode="w", format=container) as out:
        vs = out.add_stream("mpeg4", rate=FPS) if video else None
        if vs is not None:
            vs.width, vs.height, vs.pix_fmt = WIDTH, HEIGHT, "yuv420p"
            vs.codec_context.gop_size = FPS * 10
            vs.codec_context.max_b_frames = 0
        audio_stream = out.add_stream("pcm_s16le", rate=16000, layout="mono") if audio else None
        total = sum(seconds for _, seconds in scenes)
        shades = [(240, 240, 240), (110, 150, 110), (190, 100, 100), (70, 70, 160)]
        index = 0
        if vs is not None:
            for scene, (text, seconds) in enumerate(scenes):
                board = _board(text, shades[scene % len(shades)])
                for _ in range(seconds * FPS):
                    frame = av.VideoFrame.from_image(board)
                    frame.pts = index
                    frame.time_base = Fraction(1, FPS)
                    index += 1
                    for packet in vs.encode(frame):
                        out.mux(packet)
            for packet in vs.encode(None):
                out.mux(packet)
        if audio_stream is not None:
            import numpy as np

            samples = 1024
            pts = 0
            while pts < total * 16000:
                frame = av.AudioFrame.from_ndarray(np.zeros((1, samples), dtype="int16"), format="s16", layout="mono")
                frame.sample_rate = 16000
                frame.pts = pts
                frame.time_base = Fraction(1, 16000)
                pts += samples
                for packet in audio_stream.encode(frame):
                    out.mux(packet)
            for packet in audio_stream.encode(None):
                out.mux(packet)
    return buffer.getvalue()
