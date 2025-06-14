import gradio as gr

from sd_forge.modules import scripts, sd_models
from sd_forge.modules.infotext_utils import PasteField
from sd_forge.modules.ui_common import create_refresh_button
from sd_forge.modules.ui_components import InputAccordion


class ScriptRefiner(scripts.ScriptBuiltinUI):
    section = "accordions"
    create_group = False

    def __init__(self):
        pass

    def title(self):
        return "Refiner"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with InputAccordion(False, label="Refiner", elem_id=self.elem_id("enable")) as enable_refiner:
            with gr.Row():
                refiner_checkpoint = gr.Dropdown(label='Checkpoint', info='(use model of same architecture)', elem_id=self.elem_id("checkpoint"), choices=["", *sd_models.checkpoint_tiles(use_short=True)], value='', tooltip="switch to another model in the middle of generation")
                create_refresh_button(refiner_checkpoint, sd_models.list_models, lambda: {"choices": sd_models.checkpoint_tiles(use_short=True)}, self.elem_id("checkpoint_refresh"))
        
                refiner_switch_at = gr.Slider(value=0.8, label="Switch at", minimum=0.01, maximum=1.0, step=0.01, elem_id=self.elem_id("switch_at"), tooltip="fraction of sampling steps when the switch to refiner model should happen; 1=never, 0.5=switch in the middle of generation")
        
        def lookup_checkpoint(title):
            info = sd_models.get_closet_checkpoint_match(title)
            return None if info is None else info.short_title
        
        self.infotext_fields = [
            PasteField(enable_refiner, lambda d: 'Refiner' in d),
            PasteField(refiner_checkpoint, lambda d: lookup_checkpoint(d.get('Refiner')), api="refiner_checkpoint"),
            PasteField(refiner_switch_at, 'Refiner switch at', api="refiner_switch_at"),
        ]

        return enable_refiner, refiner_checkpoint, refiner_switch_at

    def setup(self, p, enable_refiner, refiner_checkpoint, refiner_switch_at):
        # the actual implementation is in sd_samplers_common.py, apply_refiner
        if not enable_refiner or refiner_checkpoint in (None, "", "None"):
            p.refiner_checkpoint = None
            p.refiner_switch_at = None
        else:
            p.refiner_checkpoint = refiner_checkpoint
            p.refiner_switch_at = refiner_switch_at
