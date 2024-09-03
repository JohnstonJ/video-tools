import os

from setuptools import setup

if os.getenv("MYPYC_ENABLE", "").lower() in ["true", "t", "1"]:
    from mypyc.build import mypycify

    ext_modules = mypycify(
        [
            "src/video_tools/dv/block",
            "--exclude",
            "binary_types.py",
        ]
    )
else:
    ext_modules = []

setup(
    ext_modules=ext_modules,
)
