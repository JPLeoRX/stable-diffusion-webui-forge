import os
import re

import torch
import numpy as np

from sd_forge.modules import modelloader, paths, deepbooru_model, images, shared
from sd_forge.backend import memory_management
from sd_forge.backend.patcher.base import ModelPatcher


re_special = re.compile(r'([\\()])')


class DeepDanbooru:
    def __init__(self):
        self.model = None
        self.load_device = memory_management.text_encoder_device()
        self.offload_device = memory_management.text_encoder_offload_device()
        self.dtype = torch.float32

        if memory_management.should_use_fp16(device=self.load_device):
            self.dtype = torch.float16

        self.patcher = None

    def load(self):
        if self.model is not None:
            return

        files = modelloader.load_models(
            model_path=os.path.join(paths.models_path, "torch_deepdanbooru"),
            model_url='https://github.com/AUTOMATIC1111/TorchDeepDanbooru/releases/download/v1/model-resnet_custom_v3.pt',
            ext_filter=[".pt"],
            download_name='model-resnet_custom_v3.pt',
        )

        self.model = deepbooru_model.DeepDanbooruModel()
        self.model.load_state_dict(torch.load(files[0], map_location="cpu"))

        self.model.eval()
        self.model.to(self.offload_device, self.dtype)

        self.patcher = ModelPatcher(self.model, load_device=self.load_device, offload_device=self.offload_device)

    def start(self):
        self.load()
        memory_management.load_models_gpu([self.patcher])

    def stop(self):
        pass

    def tag(self, pil_image):
        self.start()
        res = self.tag_multi(pil_image)
        self.stop()

        return res

    def tag_multi(self, pil_image, force_disable_ranks=False):
        threshold = shared.opts.interrogate_deepbooru_score_threshold
        use_spaces = shared.opts.deepbooru_use_spaces
        use_escape = shared.opts.deepbooru_escape
        alpha_sort = shared.opts.deepbooru_sort_alpha
        include_ranks = shared.opts.interrogate_return_ranks and not force_disable_ranks

        pic = images.resize_image(2, pil_image.convert("RGB"), 512, 512)
        a = np.expand_dims(np.array(pic, dtype=np.float32), 0) / 255

        with torch.no_grad():
            x = torch.from_numpy(a).to(self.load_device, self.dtype)
            y = self.model(x)[0].detach().cpu().numpy()

        probability_dict = {}

        for tag, probability in zip(self.model.tags, y):
            if probability < threshold:
                continue

            if tag.startswith("rating:"):
                continue

            probability_dict[tag] = probability

        if alpha_sort:
            tags = sorted(probability_dict)
        else:
            tags = [tag for tag, _ in sorted(probability_dict.items(), key=lambda x: -x[1])]

        res = []

        filtertags = {x.strip().replace(' ', '_') for x in shared.opts.deepbooru_filter_tags.split(",")}

        for tag in [x for x in tags if x not in filtertags]:
            probability = probability_dict[tag]
            tag_outformat = tag
            if use_spaces:
                tag_outformat = tag_outformat.replace('_', ' ')
            if use_escape:
                tag_outformat = re.sub(re_special, r'\\\1', tag_outformat)
            if include_ranks:
                tag_outformat = f"({tag_outformat}:{probability:.3f})"

            res.append(tag_outformat)

        return ", ".join(res)


model = DeepDanbooru()
