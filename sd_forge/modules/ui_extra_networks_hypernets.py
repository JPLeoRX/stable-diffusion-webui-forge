import os

from sd_forge.modules import shared, ui_extra_networks
from sd_forge.modules.ui_extra_networks import quote_js
from sd_forge.modules.hashes import sha256_from_cache


class ExtraNetworksPageHypernetworks(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Hypernetworks')

    def refresh(self):
        shared.reload_hypernetworks()

    def create_item(self, name, index=None, enable_filter=True):
        full_path = shared.hypernetworks.get(name)
        if full_path is None:
            return

        path, ext = os.path.splitext(full_path)
        sha256 = sha256_from_cache(full_path, f'hypernet/{name}')
        shorthash = sha256[0:10] if sha256 else None
        search_terms = [self.search_terms_from_path(path)]
        if sha256:
            search_terms.append(sha256)
        return {
            "name": name,
            "filename": full_path,
            "shorthash": shorthash,
            "preview": self.find_preview(path),
            "description": self.find_description(path),
            "search_terms": search_terms,
            "prompt": quote_js(f"<hypernet:{name}:") + " + opts.extra_networks_default_multiplier + " + quote_js(">"),
            "local_preview": f"{path}.preview.{shared.opts.samples_format}",
            "sort_keys": {'default': index, **self.get_sort_keys(path + ext)},
        }

    def list_items(self):
        # instantiate a list to protect against concurrent modification
        names = list(shared.hypernetworks)
        for index, name in enumerate(names):
            item = self.create_item(name, index)
            if item is not None:
                yield item

    def allowed_directories_for_previews(self):
        return [shared.cmd_opts.hypernetwork_dir]

