"""
Which projection arithmetic is this Python using? Run it before spending four minutes on pipeline.py.

    python tools/fingerprint.py
    PYTHONPATH=proj_fma python tools/fingerprint.py

It prints the EPSG:5070 northing of one point in Austin, Texas. The last digits differ with the
arithmetic PROJ was compiled with, and that difference decides which tract a few boundary-hugging
highway pieces land in (WRITEUP.md, section 9):

    800570.8529844111   separate multiply and add (the pyproj wheel on Intel and AMD): scores 0.00000301
    800570.8529844118   fused multiply-add (tools/build_proj_fma.sh): the reference's arithmetic
"""
import pyproj

KNOWN = {800570.8529844111: "separate multiply and add (pyproj wheel on Intel/AMD)",
         800570.8529844118: "fused multiply-add (the reference's arithmetic)"}
x, y = pyproj.Transformer.from_crs("OGC:CRS84", "EPSG:5070", always_xy=True).transform(-97.7431, 30.2672)
print(f"pyproj {pyproj.__version__}, PROJ {pyproj.proj_version_str}, loaded from {pyproj.__file__}")
print(f"Austin northing {y!r}: {KNOWN.get(y, 'neither of the two known builds')}")
