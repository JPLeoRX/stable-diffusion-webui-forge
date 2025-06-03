import html
import sys

from sd_forge.modules import script_callbacks, scripts, ui_components
from sd_forge.modules.options import OptionHTML, OptionInfo
from sd_forge.modules.shared_cmd_options import cmd_opts


def realesrgan_models_names():
    import sd_forge.modules.realesrgan_model
    return [x.name for x in sd_forge.modules.realesrgan_model.get_realesrgan_models(None)]


def dat_models_names():
    import sd_forge.modules.dat_model
    return [x.name for x in sd_forge.modules.dat_model.get_dat_models(None)]


def postprocessing_scripts():
    import sd_forge.modules.scripts

    return sd_forge.modules.scripts.scripts_postproc.scripts


def sd_vae_items():
    import sd_forge.modules.sd_vae

    return ["Automatic", "None"] + list(sd_forge.modules.sd_vae.vae_dict)


def refresh_vae_list():
    import sd_forge.modules.sd_vae

    sd_forge.modules.sd_vae.refresh_vae_list()


def cross_attention_optimizations():
    return ["Automatic"]


def sd_unet_items():
    import sd_forge.modules.sd_unet

    return ["Automatic"] + [x.label for x in sd_forge.modules.sd_unet.unet_options] + ["None"]


def refresh_unet_list():
    import sd_forge.modules.sd_unet

    sd_forge.modules.sd_unet.list_unets()


def list_checkpoint_tiles(use_short=False):
    import sd_forge.modules.sd_models
    return sd_forge.modules.sd_models.checkpoint_tiles(use_short)


def refresh_checkpoints():
    import sd_forge.modules.sd_models
    return sd_forge.modules.sd_models.list_models()


def list_samplers():
    import sd_forge.modules.sd_samplers
    return sd_forge.modules.sd_samplers.all_samplers


def reload_hypernetworks():
    from sd_forge.modules.hypernetworks import hypernetwork
    from sd_forge.modules import shared

    shared.hypernetworks = hypernetwork.list_hypernetworks(cmd_opts.hypernetwork_dir)


def get_infotext_names():
    from sd_forge.modules import infotext_utils, shared
    res = {}

    for info in shared.opts.data_labels.values():
        if info.infotext:
            res[info.infotext] = 1

    for tab_data in infotext_utils.paste_fields.values():
        for _, name in tab_data.get("fields") or []:
            if isinstance(name, str):
                res[name] = 1

    res['Lora hashes'] = 1

    return list(res)


ui_reorder_categories_builtin_items = [
    "prompt",
    "image",
    "inpaint",
    "sampler",
    "accordions",
    "checkboxes",
    "dimensions",
    "cfg",
    "denoising",
    "seed",
    "batch",
    "override_settings",
]


def ui_reorder_categories():
    from sd_forge.modules import scripts

    yield from ui_reorder_categories_builtin_items

    sections = {}
    for script in scripts.scripts_txt2img.scripts + scripts.scripts_img2img.scripts:
        if isinstance(script.section, str) and script.section not in ui_reorder_categories_builtin_items:
            sections[script.section] = 1

    yield from sections

    yield "scripts"


def callbacks_order_settings():
    options = {
        "sd_vae_explanation": OptionHTML("""
    For categories below, callbacks added to dropdowns happen before others, in order listed.
    """),

    }

    callback_options = {}

    for category, _ in script_callbacks.enumerate_callbacks():
        callback_options[category] = script_callbacks.ordered_callbacks(category, enable_user_sort=False)

    for method_name in scripts.scripts_txt2img.callback_names:
        callback_options["script_" + method_name] = scripts.scripts_txt2img.create_ordered_callbacks_list(method_name, enable_user_sort=False)

    for method_name in scripts.scripts_img2img.callback_names:
        callbacks = callback_options.get("script_" + method_name, [])

        for addition in scripts.scripts_img2img.create_ordered_callbacks_list(method_name, enable_user_sort=False):
            if any(x.name == addition.name for x in callbacks):
                continue

            callbacks.append(addition)

        callback_options["script_" + method_name] = callbacks

    for category, callbacks in callback_options.items():
        if not callbacks:
            continue

        option_info = OptionInfo([], f"{category} callback priority", ui_components.DropdownMulti, {"choices": [x.name for x in callbacks]})
        option_info.needs_restart()
        option_info.html("<div class='info'>Default order: <ol>" + "".join(f"<li>{html.escape(x.name)}</li>\n" for x in callbacks) + "</ol></div>")
        options['prioritized_callbacks_' + category] = option_info

    return options


class Shared(sys.modules[__name__].__class__):
    """
    this class is here to provide sd_model field as a property, so that it can be created and loaded on demand rather than
    at program startup.
    """

    sd_model_val = None

    @property
    def sd_model(self):
        import sd_forge.modules.sd_models

        return sd_forge.modules.sd_models.model_data.get_sd_model()

    @sd_model.setter
    def sd_model(self, value):
        import sd_forge.modules.sd_models

        sd_forge.modules.sd_models.model_data.set_sd_model(value)


sys.modules['sd_forge.modules.shared'].__class__ = Shared
