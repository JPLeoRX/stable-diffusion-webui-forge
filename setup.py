from setuptools import setup, find_packages


setup_args = dict(
    name="sd_forge",
    version="0.0.1",
    description="Stable-Diffusion WebUI Forge packaged as a reusable Python dependency",
    keywords=[],
    long_description="",
    long_description_content_type="text/markdown",
    author="Automatic1111 & Forge authors",
    url="https://github.com/JPLeoRX/stable-diffusion-webui-forge",
    packages=find_packages(),
    include_package_data=True,          # let MANIFEST.in add non-py files
)

install_requires=[],

if __name__ == '__main__':
    setup(**setup_args, install_requires=install_requires)
