from nodes import SaveImage
import hashlib
import asyncio
import json
import base64
import os
import time
import torch
import numpy as np
from PIL import Image, ImageOps
from io import BytesIO
import folder_paths
import sys
import torchvision.transforms.functional as tf
import aiohttp
import socket
import requests
import functools


sys.stdout.reconfigure(encoding="utf-8")
nodepath = os.path.join(
    folder_paths.get_folder_paths("custom_nodes")[0], "comfyui-photoshop"
)

# region SERVER Utilities
class IPChecker:
    def __init__(self):
        self.ips = list(self.get_local_ips())
        self.checked_ips = set()

    def get_working_ip(self, test_url_template):
        for ip in self.ips:
            if ip not in self.checked_ips:
                self.checked_ips.add(ip)
                test_url = test_url_template.format(ip)
                if self._test_url(test_url):
                    return ip
        return None

    @staticmethod
    def get_local_ips(prefix="192.168."):
        hostname = socket.gethostname()
        print(f"[ComfyUIToPhotoshop] Getting local ips for {hostname}")
        for info in socket.getaddrinfo(hostname, None):
            # Filter out IPv6 addresses if you only want IPv4
            # if info[1] == socket.SOCK_STREAM and
            if info[0] == socket.AF_INET and info[4][0].startswith(prefix):
                yield info[4][0]

    def _test_url(self, url):
        try:
            response = requests.get(url)
            return response.status_code == 200
        except Exception:
            return False


@functools.lru_cache(maxsize=1)
def get_server_info():
    from comfy.cli_args import args

    ip_checker = IPChecker()
    base_url = args.listen
    if base_url == "0.0.0.0":
        base_url = socket.gethostname()
        # print("Server set to 0.0.0.0, we will try to resolve the host IP")
        # base_url = ip_checker.get_working_ip(
        #     f"http://{{}}:{args.port}/history"
        # )
        # print(f"[ComfyUIToPhotoshop] Setting ip to {base_url}")
    return (base_url, args.port)

def is_changed_file(filepath):
    try:
        with open(filepath, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        if not hasattr(is_changed_file, "file_hashes"):
            is_changed_file.file_hashes = {}
        if filepath in is_changed_file.file_hashes:
            if is_changed_file.file_hashes[filepath] == file_hash:
                return False
        is_changed_file.file_hashes[filepath] = file_hash
        return float("NaN")
    except Exception as e:
        print(f"Error in is_changed_file for {filepath}: {e}")
        return False


class PhotoshopToComfyUI:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ("IMAGE", "MASK", "FLOAT", "FLOAT", "INT", "STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("Canvas", "Mask", "Slider", "Slider2", "Seed", "+", "-", "W", "H")
    FUNCTION = "PS_Execute"
    CATEGORY = "Photoshop"

    def PS_Execute(self):
        self.LoadDir()
        self.loadConfig()
        self.SendImg()

        sliderValue = self.slider / 100
        slider2Value = self.slider2 / 100

        return (
            self.canvas,
            self.mask.unsqueeze(0),
            sliderValue,
            slider2Value,
            int(self.seed),
            self.psPrompt,
            self.ngPrompt,
            int(self.width),
            int(self.height),
        )

    def LoadDir(self, retry_count=0):
        try:
            self.canvasDir = os.path.join(
                nodepath, "data", "ps_inputs", "PS_canvas.png"
            )
            self.maskImgDir = os.path.join(nodepath, "data", "ps_inputs", "PS_mask.png")
            self.configJson = os.path.join(nodepath, "data", "ps_inputs", "config.json")
        except:
            time.sleep(0.5)
            if retry_count < 4:
                self.LoadDir(retry_count + 1)
            else:
                raise Exception(
                    "Failed to load directory after 5 attempts. \n 🔴 Make sure you have installed and started the Photoshop Plugin Successfully. \n 🔴 otherwise you can restart your Photoshop and your plugin to fix this problem."
                )

    def loadConfig(self, retry_count=0):
        try:
            with open(self.configJson, "r", encoding="utf-8") as file:
                self.ConfigData = json.load(file)
        except:
            time.sleep(0.5)
            if retry_count < 4:
                self.loadConfig(retry_count + 1)
            else:
                raise Exception(
                    "Failed to load config after 5 attempts. \n 🔴 Make sure you have installed and started the Photoshop Plugin Successfully. \n 🔴 otherwise you can restart your Photoshop and your plugin to fix this problem."
                )

        self.psPrompt = self.ConfigData["positive"]
        self.ngPrompt = self.ConfigData["negative"]
        self.seed = self.ConfigData["seed"]
        self.slider = self.ConfigData["slider"]
        self.slider2 = self.ConfigData["slider2"]

    def SendImg(self):
        self.loadImg(self.canvasDir)
        self.canvas = self.i.convert("RGB")
        self.canvas = np.array(self.canvas).astype(np.float32) / 255.0
        self.canvas = torch.from_numpy(self.canvas)[None,]
        self.width, self.height = self.i.size

        self.loadImg(self.maskImgDir)
        self.i = ImageOps.exif_transpose(self.i)
        self.mask = np.array(self.i.getchannel("B")).astype(np.float32) / 255.0
        self.mask = torch.from_numpy(self.mask)

        # Convert #010101 to #000000
        self.mask = self.mask.numpy()  # Convert to numpy array for easier manipulation
        target_color = 1 / 255.0  # The float representation of #010101
        self.mask[self.mask == target_color] = 0.0  # Change target_color to 0.0
        self.mask = torch.from_numpy(self.mask)

    def loadImg(self, path):
        try:
            with open(path, "rb") as file:
                img_data = file.read()
            self.i = Image.open(BytesIO(img_data))
            self.i.verify()
            self.i = Image.open(BytesIO(img_data))
        except:
            self.i = Image.new(mode="RGB", size=(24, 24), color=(0, 0, 0))
        if not self.i:
            return

    @classmethod
    def IS_CHANGED(cls):
        try:
            configJson = os.path.join(nodepath, "data", "ps_inputs", "config.json")
            canvasDir = os.path.join(nodepath, "data", "ps_inputs", "PS_canvas.png")
            maskImgDir = os.path.join(nodepath, "data", "ps_inputs", "PS_mask.png")

            config_changed = is_changed_file(configJson)
            canvas_changed = is_changed_file(canvasDir)
            mask_changed = is_changed_file(maskImgDir)

            return config_changed or canvas_changed or mask_changed
        except Exception as e:
            print("Error in IS_CHANGED:", e)
            return 0


class ComfyUIToPhotoshop(SaveImage):
    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix_append = "_temp_"
        self.compress_level = 4

    @staticmethod
    def INPUT_TYPES():
        return {
            "required": {
                "output": ("IMAGE",),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    FUNCTION = "execute"
    CATEGORY = "Photoshop"

    async def connect_to_backend(self, filename):
        try:
            base_url, port = get_server_info()
            url = f"http://{base_url}:{port}/ps/renderdone?filename={filename}"
            print(f"[ComfyUIToPhotoshop] Connecting to backend at {url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.text()
        except Exception as e:
            print(f"_PS_ error on send2Ps: {e}")

    def execute(
        self,
        output: torch.Tensor,
        filename_prefix="PS_OUTPUTS",
        prompt=None,
        extra_pnginfo=None,
    ):
        x = self.save_images(output, filename_prefix, prompt, extra_pnginfo)
        asyncio.run(self.connect_to_backend(x["ui"]["images"][0]["filename"]))
        return x


class ClipPass:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"clip": ("CLIP",)}}

    RETURN_TYPES = ("CLIP",)
    RETURN_NAMES = ("clip",)
    FUNCTION = "exe"
    CATEGORY = "utils"

    def exe(self, clip):
        return (clip,)


class modelPass:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"model": ("MODEL",)}}

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("model",)
    FUNCTION = "exe"
    CATEGORY = "utils"

    def exe(self, model):
        return (model,)


NODE_CLASS_MAPPINGS = {
    "🔹Photoshop ComfyUI Plugin": PhotoshopToComfyUI,
    "🔹SendTo Photoshop Plugin": ComfyUIToPhotoshop,
    "🔹ClipPass": ClipPass,
    "🔹modelPass": modelPass,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PhotoshopToComfyUI": "🔹Photoshop ComfyUI Plugin",
    "SendToPhotoshop": "🔹Send To Photoshop",
    "ClipPass": "🔹ClipPass",
    "modelPass": "🔹modelPass",
}
