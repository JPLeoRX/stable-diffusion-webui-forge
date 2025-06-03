# sd_webui_forge/__init__.py
"""
Thin wrapper so you can:

    import sd_webui_forge as forge
    img = forge.txt2img(...)
"""

# from modules import initialize_util
# from modules import initialize
# from modules_forge.initialization import initialize_forge
from modules.esrgan_model import UpscalerESRGAN

__all__ = [
    # initialize_util, initialize, initialize_forge,
    UpscalerESRGAN,
]
