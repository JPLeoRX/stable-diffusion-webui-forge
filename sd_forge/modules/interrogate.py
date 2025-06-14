import os
import sys
from collections import namedtuple
from pathlib import Path
import re

import torch
import torch.hub

from torchvision import transforms
from torchvision.transforms.functional import InterpolationMode

from sd_forge.modules import devices, paths, shared, modelloader, errors
from sd_forge.backend import memory_management
from sd_forge.backend.patcher.base import ModelPatcher


blip_image_eval_size = 384
clip_model_name = 'ViT-L/14'

Category = namedtuple("Category", ["name", "topn", "items"])

re_topn = re.compile(r"\.top(\d+)$")

def category_types():
    return [f.stem for f in Path(shared.interrogator.content_dir).glob('*.txt')]


def download_default_clip_interrogate_categories(content_dir):
    print("Downloading CLIP categories...")

    tmpdir = f"{content_dir}_tmp"
    category_types = ["artists", "flavors", "mediums", "movements"]

    try:
        os.makedirs(tmpdir, exist_ok=True)
        for category_type in category_types:
            torch.hub.download_url_to_file(f"https://raw.githubusercontent.com/pharmapsychotic/clip-interrogator/main/clip_interrogator/data/{category_type}.txt", os.path.join(tmpdir, f"{category_type}.txt"))
        os.rename(tmpdir, content_dir)

    except Exception as e:
        errors.display(e, "downloading default CLIP interrogate categories")
    finally:
        if os.path.exists(tmpdir):
            os.removedirs(tmpdir)


class InterrogateModels:
    blip_model = None
    clip_model = None
    clip_preprocess = None
    dtype = None
    running_on_cpu = None

    def __init__(self, content_dir):
        self.loaded_categories = None
        self.skip_categories = []
        self.content_dir = content_dir

        self.load_device = memory_management.text_encoder_device()
        self.offload_device = memory_management.text_encoder_offload_device()
        self.dtype = torch.float32

        if memory_management.should_use_fp16(device=self.load_device):
            self.dtype = torch.float16

        self.blip_patcher = None
        self.clip_patcher = None

    def categories(self):
        if not os.path.exists(self.content_dir):
            download_default_clip_interrogate_categories(self.content_dir)

        if self.loaded_categories is not None and self.skip_categories == shared.opts.interrogate_clip_skip_categories:
           return self.loaded_categories

        self.loaded_categories = []

        if os.path.exists(self.content_dir):
            self.skip_categories = shared.opts.interrogate_clip_skip_categories
            category_types = []
            for filename in Path(self.content_dir).glob('*.txt'):
                category_types.append(filename.stem)
                if filename.stem in self.skip_categories:
                    continue
                m = re_topn.search(filename.stem)
                topn = 1 if m is None else int(m.group(1))
                with open(filename, "r", encoding="utf8") as file:
                    lines = [x.strip() for x in file.readlines()]

                self.loaded_categories.append(Category(name=filename.stem, topn=topn, items=lines))

        return self.loaded_categories

    def create_fake_fairscale(self):
        class FakeFairscale:
            def checkpoint_wrapper(self):
                pass

        sys.modules["fairscale.nn.checkpoint.checkpoint_activations"] = FakeFairscale

    def load_blip_model(self):
        self.create_fake_fairscale()
        import models.blip

        files = modelloader.load_models(
            model_path=os.path.join(paths.models_path, "BLIP"),
            model_url='https://storage.googleapis.com/sfr-vision-language-research/BLIP/models/model_base_caption_capfilt_large.pth',
            ext_filter=[".pth"],
            download_name='model_base_caption_capfilt_large.pth',
        )

        blip_model = models.blip.blip_decoder(pretrained=files[0], image_size=blip_image_eval_size, vit='base', med_config=os.path.join(paths.paths["BLIP"], "configs", "med_config.json"))
        blip_model.eval()

        return blip_model

    def load_clip_model(self):
        import clip
        import clip.model

        clip.model.LayerNorm = torch.nn.LayerNorm

        model, preprocess = clip.load(clip_model_name, device="cpu", download_root=shared.cmd_opts.clip_models_path)
        model.eval()

        return model, preprocess

    def load(self):
        if self.blip_model is None:
            self.blip_model = self.load_blip_model()
            self.blip_model = self.blip_model.to(device=self.offload_device, dtype=self.dtype)
            self.blip_patcher = ModelPatcher(self.blip_model, load_device=self.load_device, offload_device=self.offload_device)

        if self.clip_model is None:
            self.clip_model, self.clip_preprocess = self.load_clip_model()
            self.clip_model = self.clip_model.to(device=self.offload_device, dtype=self.dtype)
            self.clip_patcher = ModelPatcher(self.clip_model, load_device=self.load_device, offload_device=self.offload_device)

        memory_management.load_models_gpu([self.blip_patcher, self.clip_patcher])
        return

    def send_clip_to_ram(self):
        pass

    def send_blip_to_ram(self):
        pass

    def unload(self):
        pass

    def rank(self, image_features, text_array, top_count=1):
        import clip

        devices.torch_gc()

        if shared.opts.interrogate_clip_dict_limit != 0:
            text_array = text_array[0:int(shared.opts.interrogate_clip_dict_limit)]

        top_count = min(top_count, len(text_array))
        text_tokens = clip.tokenize(list(text_array), truncate=True).to(self.load_device)
        text_features = self.clip_model.encode_text(text_tokens).type(self.dtype)
        text_features /= text_features.norm(dim=-1, keepdim=True)

        similarity = torch.zeros((1, len(text_array))).to(self.load_device)
        for i in range(image_features.shape[0]):
            similarity += (100.0 * image_features[i].unsqueeze(0) @ text_features.T).softmax(dim=-1)
        similarity /= image_features.shape[0]

        top_probs, top_labels = similarity.cpu().topk(top_count, dim=-1)
        return [(text_array[top_labels[0][i].numpy()], (top_probs[0][i].numpy()*100)) for i in range(top_count)]

    def generate_caption(self, pil_image):
        gpu_image = transforms.Compose([
            transforms.Resize((blip_image_eval_size, blip_image_eval_size), interpolation=InterpolationMode.BICUBIC),
            transforms.ToTensor(),
            transforms.Normalize((0.48145466, 0.4578275, 0.40821073), (0.26862954, 0.26130258, 0.27577711))
        ])(pil_image).unsqueeze(0).type(self.dtype).to(self.load_device)

        with torch.no_grad():
            caption = self.blip_model.generate(gpu_image, sample=False, num_beams=int(shared.opts.interrogate_clip_num_beams), min_length=int(shared.opts.interrogate_clip_min_length), max_length=shared.opts.interrogate_clip_max_length)

        return caption[0]

    def interrogate(self, pil_image):
        res = ""
        shared.state.begin(job="interrogate")
        try:
            self.load()

            caption = self.generate_caption(pil_image)
            self.send_blip_to_ram()
            devices.torch_gc()

            res = caption

            clip_image = self.clip_preprocess(pil_image).unsqueeze(0).type(self.dtype).to(self.load_device)

            with torch.no_grad(), devices.autocast():
                image_features = self.clip_model.encode_image(clip_image).type(self.dtype)

                image_features /= image_features.norm(dim=-1, keepdim=True)

                for cat in self.categories():
                    matches = self.rank(image_features, cat.items, top_count=cat.topn)
                    for match, score in matches:
                        if shared.opts.interrogate_return_ranks:
                            res += f", ({match}:{score/100:.3f})"
                        else:
                            res += f", {match}"

        except Exception:
            errors.report("Error interrogating", exc_info=True)
            res += "<error>"

        self.unload()
        shared.state.end()

        return res
