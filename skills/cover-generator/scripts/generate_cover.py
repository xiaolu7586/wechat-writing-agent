#!/usr/bin/env python3
"""
封面图生成器

使用 Seedream 5.0 Lite 生成封面图。

认证优先级：
  1. .secrets/image-config.json（用户配置，推荐）
  2. 环境变量 IMAGE_API_KEY / IMAGE_BASE_URL
  3. ~/.easyclaw/ 运行时（EasyClaw 平台自动注入）
EasyClaw API 不可用或显式跳过 AI 时，使用 Picsum Photos 随机图。

Usage:
    # AI 生成
    python3 generate_cover.py --title "文章标题" -o cover.jpg

    # 跳过 AI，直接使用随机图
    python3 generate_cover.py --title "文章标题" --no-ai -o cover.jpg

    # 指定尺寸
    python3 generate_cover.py --title "文章标题" --size 1280*720 -o cover.jpg

    # 自定义 AI 提示词
    python3 generate_cover.py --title "文章标题" --prompt "赛博朋克城市夜景" -o cover.jpg
"""

from __future__ import annotations

import subprocess
import sys


def _ensure_deps() -> None:
    """Auto-install missing packages on first run. Zero overhead if already installed."""
    needed = {"openai": "openai", "PIL": "Pillow"}
    missing = []
    for imp, pkg in needed.items():
        try:
            __import__(imp)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[Setup] Installing: {', '.join(missing)} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + missing)
        print("[Setup] Done.")


_ensure_deps()


import argparse
import base64
import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from PIL import Image as PILImage

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

MODEL_NAME = "bytepluses.seedream-5.0-lite"
PLACEHOLDER_API_KEY = "easyclaw-placeholder"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "output" / "covers"
SCRIPT_DIR = Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent.parent.parent.parent
SECRETS_PATH = WORKSPACE_ROOT / ".secrets" / "image-config.json"
DEFAULT_SIZE = "1280*720"  # 微信公众号推荐比例
MAX_REF_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

# size → aspect-ratio 映射
SIZE_TO_ASPECT = {
    "800*600": "4:3",
    "600*800": "3:4",
    "1280*720": "16:9",
    "720*1280": "9:16",
    "1200*630": "16:9",
}

# 风格预设（完整视觉配方，覆盖光影/材质/色调/镜头/构图）
STYLE_ENHANCEMENTS = {
    # --- 通用风格 ---
    "editorial": (
        "editorial magazine photography, rule-of-thirds composition, "
        "soft diffused studio lighting with subtle rim light, "
        "shallow depth of field 85mm f/1.4, muted desaturated tones, "
        "clean negative space, film grain texture, professional color grading"
    ),
    "cinematic": (
        "cinematic film still, wide 16:9 anamorphic composition, "
        "golden hour warm directional lighting with lens flare, "
        "rich contrast deep shadows, teal-and-orange color grading, "
        "50mm prime lens bokeh, atmospheric haze, movie scene mood"
    ),
    "minimal": (
        "ultra-minimalist flat design, centered balanced composition, "
        "even ambient soft lighting no harsh shadows, "
        "limited color palette 2-3 muted tones, generous whitespace, "
        "clean geometric shapes, Scandinavian aesthetic"
    ),
    "warm": (
        "warm lifestyle photography, natural window light golden tones, "
        "soft focus cozy atmosphere, earth tones palette cream beige amber, "
        "35mm wide angle, relaxed candid composition, "
        "linen texture organic feel, hygge aesthetic"
    ),
    "tech": (
        "futuristic technology visualization, dynamic diagonal composition, "
        "cool blue-purple neon accent lighting on dark background, "
        "metallic chrome reflective surfaces, holographic elements, "
        "wide angle 24mm perspective, clean digital precision"
    ),
    "bold": (
        "high-impact graphic design, strong diagonal composition, "
        "dramatic chiaroscuro single directional hard light, "
        "high contrast vibrant saturated primary colors, "
        "sharp edges geometric blocks, contemporary art direction"
    ),
    # --- 领域特化风格 ---
    "finance": (
        "professional business photography, clean symmetric composition, "
        "soft overhead studio lighting, muted navy-gray-gold palette, "
        "sleek modern surfaces glass and marble texture, "
        "medium telephoto 70mm, authoritative and trustworthy mood"
    ),
    "lifestyle": (
        "natural lifestyle editorial, relaxed off-center composition, "
        "soft diffused daylight warm undertones, "
        "pastel earth palette sage cream terracotta, "
        "light airy feel with subtle lens flare, 35mm candid"
    ),
    "education": (
        "bright educational illustration style, clear structured layout, "
        "even flat lighting no shadows, cheerful warm color palette, "
        "clean simple shapes with rounded edges, "
        "isometric or flat perspective, friendly approachable mood"
    ),
}
# "modern" 兼容旧调用，映射到 editorial
STYLE_ENHANCEMENTS["modern"] = STYLE_ENHANCEMENTS["editorial"]

# 质量后缀（自动追加到所有 prompt 末尾）
DEFAULT_QUALITY_SUFFIX = (
    "no text, no watermark, no signature, no letters, no words, "
    "high quality, 4K detail, professional photography"
)

# 默认负面提示词
DEFAULT_NEGATIVE_PROMPT = (
    "text, watermark, signature, letters, words, label, caption, "
    "ugly, blurry, low quality, low resolution, pixelated, "
    "oversaturated, cartoon unless intended, stock photo generic, "
    "cluttered, busy, messy, multiple borders, frames"
)

# aspect-ratio → Seedream 2K 精确像素尺寸（来自官方文档）
ASPECT_TO_PIXELS = {
    "1:1":  "2048x2048",
    "4:3":  "2304x1728",
    "3:4":  "1728x2304",
    "16:9": "2848x1600",
    "9:16": "1600x2848",
    "3:2":  "2496x1664",
    "2:3":  "1664x2496",
    "21:9": "3136x1344",
}

SUPPORTED_ASPECT_RATIOS = ["2:3", "3:2", "3:4", "4:3", "9:16", "16:9", "21:9"]

# ---------------------------------------------------------------------------
# 安全过滤（敏感内容关键词拦截）
# ---------------------------------------------------------------------------

BLOCKED_KEYWORDS = [
    # 政治人物与事件
    "习近平", "毛泽东", "邓小平", "江泽民", "胡锦涛", "李克强",
    "天安门事件", "六四", "文化大革命", "法轮功",
    "xi jinping", "mao zedong", "tiananmen",
    # 色情
    "裸体", "色情", "性爱", "porn", "nude", "naked", "sexual", "hentai", "nsfw",
    # 暴力
    "杀人", "砍人", "血腥", "酷刑", "斩首", "gore", "torture", "beheading",
    # 赌博
    "赌博", "赌场", "casino", "gambling",
    # 毒品
    "吸毒", "毒品", "大麻", "cocaine", "heroin", "冰毒",
    # 儿童安全
    "儿童色情", "child porn", "underage",
    # 歧视
    "纳粹", "nazi", "swastika",
]


def check_prompt_safety(prompt: str) -> tuple[bool, str]:
    """检查提示词是否包含敏感内容。返回 (is_safe, matched_keyword)。"""
    prompt_lower = prompt.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword.lower() in prompt_lower:
            return False, keyword
    return True, ""


# ---------------------------------------------------------------------------
# EasyClaw 运行时配置
# ---------------------------------------------------------------------------

class ConfigError(RuntimeError):
    """Raised when required EasyClaw configuration is missing or invalid."""


def resolve_state_dir(home_dir: Path | None = None) -> Path:
    return (home_dir or Path.home()) / ".easyclaw"


def load_json_file(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ConfigError(f"Missing required file: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"Invalid JSON in file: {path}") from error


def normalize_base_url(value: str) -> str:
    trimmed = value.strip().rstrip("/")
    if not trimmed:
        raise ConfigError("easyclaw baseUrl must be a non-empty string")
    return trimmed


def extract_base_url_from_config(config_data: object) -> str:
    if not isinstance(config_data, dict):
        raise ConfigError("easyclaw config must be a JSON object")

    models = config_data.get("models")
    if not isinstance(models, dict):
        raise ConfigError("easyclaw config missing models.providers.easyclaw.baseUrl")

    providers = models.get("providers")
    if not isinstance(providers, dict):
        raise ConfigError("easyclaw config missing models.providers.easyclaw.baseUrl")

    easyclaw = providers.get("easyclaw")
    if not isinstance(easyclaw, dict):
        raise ConfigError("easyclaw config missing models.providers.easyclaw.baseUrl")

    base_url_val = easyclaw.get("baseUrl")
    if not isinstance(base_url_val, str) or not base_url_val.strip():
        raise ConfigError("easyclaw config missing models.providers.easyclaw.baseUrl")

    return normalize_base_url(base_url_val)


def extract_auth_from_userinfo(userinfo_data: object) -> tuple[str, str]:
    if not isinstance(userinfo_data, dict):
        raise ConfigError("easyclaw userinfo must be a JSON object")

    uid = userinfo_data.get("uid")
    token = userinfo_data.get("token")
    if not isinstance(uid, str) or not uid.strip():
        raise ConfigError("easyclaw userinfo invalid: uid must be a non-empty string")
    if not isinstance(token, str) or not token.strip():
        raise ConfigError("easyclaw userinfo invalid: token must be a non-empty string")
    return uid.strip(), token.strip()


def load_easyclaw_runtime_config(state_dir: Path) -> tuple[str, str, str]:
    config_path = state_dir / "easyclaw.json"
    userinfo_path = state_dir / "identity" / "easyclaw-userinfo.json"
    base_url = extract_base_url_from_config(load_json_file(config_path))
    uid, token = extract_auth_from_userinfo(load_json_file(userinfo_path))
    return base_url, uid, token


def build_openai_client(base_url: str, uid: str, token: str) -> OpenAI:
    return OpenAI(
        api_key=PLACEHOLDER_API_KEY,
        base_url=normalize_base_url(base_url),
        default_headers={
            "X-Auth-Uid": uid,
            "X-Auth-Token": token,
        },
    )



def upload_to_transfer_sh(file_path: Path) -> str | None:
    """Upload file to a public hosting service and return URL. Tries multiple services."""
    import urllib.request as urlreq

    with open(file_path, "rb") as f:
        data = f.read()

    # Try transfer.sh
    try:
        req = urlreq.Request(
            f"https://transfer.sh/{file_path.name}",
            data=data, method="PUT"
        )
        req.add_header("Max-Days", "14")
        with urlreq.urlopen(req, timeout=30) as resp:
            url = resp.read().decode().strip()
            if url.startswith("http"):
                return url
    except Exception:
        pass

    # Try 0x0.st as fallback
    try:
        import subprocess
        result = subprocess.run(
            ["curl", "-s", "-F", f"file=@{file_path}", "https://0x0.st"],
            capture_output=True, text=True, timeout=30
        )
        url = result.stdout.strip()
        if url.startswith("http"):
            return url
    except Exception:
        pass

    return None

def load_image_auth() -> tuple[str, str, str, str] | None:
    """
    Load image generation credentials with priority:
      1. .secrets/image-config.json  (user-configured via formData)
      2. Environment variables: IMAGE_API_KEY, IMAGE_BASE_URL
      3. ~/.easyclaw/ runtime (platform auto-inject)
    Returns (base_url, api_key, model, auth_type) or None if nothing found.
    """
    import os

    def _detect_model(base_url: str, override: str) -> str:
        if override:
            return override
        if "googleapis.com" in base_url:
            return "imagen-3.0-generate-001"
        return "dall-e-3"

    def _std_base_url(base_url: str) -> str:
        return base_url.strip().rstrip("/") if base_url.strip() else "https://api.openai.com/v1"

    # Priority 1: .secrets/image-config.json
    if SECRETS_PATH.is_file():
        try:
            cfg = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
            api_key = cfg.get("image_api_key", "").strip()
            base_url = _std_base_url(cfg.get("image_base_url", ""))
            model = _detect_model(base_url, cfg.get("image_model", "").strip())
            if api_key:
                return base_url, api_key, model, "secrets"
        except Exception:
            pass

    # Priority 2: environment variables
    api_key = os.environ.get("IMAGE_API_KEY", "").strip()
    if api_key:
        base_url = _std_base_url(os.environ.get("IMAGE_BASE_URL", ""))
        model = _detect_model(base_url, os.environ.get("IMAGE_MODEL", "").strip())
        return base_url, api_key, model, "env"

    # Priority 3: EasyClaw runtime
    state_dir = resolve_state_dir()
    try:
        ec_base_url, uid, token = load_easyclaw_runtime_config(state_dir)
        return ec_base_url, f"{uid}:{token}", MODEL_NAME, "easyclaw"
    except ConfigError:
        pass

    return None


# ---------------------------------------------------------------------------
# size → aspect-ratio 转换
# ---------------------------------------------------------------------------

def size_to_aspect_ratio(size: str) -> str:
    """将 宽*高 尺寸转换为 aspect-ratio 字符串。"""
    if size in SIZE_TO_ASPECT:
        return SIZE_TO_ASPECT[size]

    try:
        w, h = (int(x) for x in size.split("*"))
    except ValueError:
        return "16:9"  # 封面默认 16:9

    ratio = w / h
    candidates = {
        "3:4": 3 / 4,
        "4:3": 4 / 3,
        "2:3": 2 / 3,
        "3:2": 3 / 2,
        "9:16": 9 / 16,
        "16:9": 16 / 9,
        "21:9": 21 / 9,
    }
    return min(candidates, key=lambda k: abs(candidates[k] - ratio))


# ---------------------------------------------------------------------------
# 图片保存
# ---------------------------------------------------------------------------

def load_reference_image(image_path: Path) -> str:
    """读取参考图片并返回 data URI 格式字符串。

    支持 PNG/JPG/JPEG/WebP，超过 MAX_REF_IMAGE_SIZE 报错。
    返回格式: data:{mime};base64,{b64}
    """
    if not image_path.exists():
        raise FileNotFoundError(f"参考图片不存在: {image_path}")

    file_size = image_path.stat().st_size
    if file_size > MAX_REF_IMAGE_SIZE:
        raise ValueError(
            f"参考图片过大: {file_size / 1024 / 1024:.1f} MB，"
            f"上限 {MAX_REF_IMAGE_SIZE / 1024 / 1024:.0f} MB"
        )

    suffix = image_path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime = mime_map.get(suffix)
    if not mime:
        raise ValueError(
            f"不支持的图片格式: {suffix}，"
            f"支持: {', '.join(mime_map.keys())}"
        )

    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def save_image_from_response(response: object, output_path: Path) -> bool:
    data = getattr(response, "data", None)
    if not isinstance(data, list) or not data:
        return False

    for item in data:
        image_b64 = getattr(item, "b64_json", None)
        image_url = getattr(item, "url", None)
        if isinstance(image_b64, str) and image_b64.strip():
            output_path.write_bytes(base64.b64decode(image_b64))
            return True
        if isinstance(image_url, str) and image_url.strip():
            download_file(image_url, output_path)
            return True
    return False


def download_file(url: str, output_path: Path) -> None:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            output_path.write_bytes(response.read())
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Download failed ({error.code}): {payload}") from error


def crop_to_aspect_ratio(image_path: Path, target_aspect: str) -> bool:
    """检查图片实际比例，不符合目标比例时从中心裁切。返回是否进行了裁切。"""
    try:
        target_w, target_h = (int(x) for x in target_aspect.split(":"))
    except (ValueError, IndexError):
        return False
    target_ratio = target_w / target_h

    with PILImage.open(image_path) as img:
        w, h = img.size
        actual_ratio = w / h
        # 允许 5% 误差
        if abs(actual_ratio - target_ratio) / target_ratio < 0.05:
            return False
        # 需要裁切：从中心裁到目标比例
        if actual_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            box = (left, 0, left + new_w, h)
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            box = (0, top, w, top + new_h)
        cropped = img.crop(box)
        cropped.save(image_path)
        print(f"[Crop] 比例修正 {target_aspect}：{w}x{h} → {cropped.size[0]}x{cropped.size[1]}")
        return True


# ---------------------------------------------------------------------------
# Picsum fallback
# ---------------------------------------------------------------------------

def fetch_picsum(size: str, output_path: Path) -> str | None:
    """Return a stable public Picsum URL — no download or upload needed."""
    import random
    try:
        width, height = (int(x) for x in size.split("*"))
    except ValueError:
        print(f"[Picsum] 尺寸格式无效：{size}")
        return None

    seed = random.randint(1, 99999)
    url = f"https://picsum.photos/seed/{seed}/{width}/{height}"
    print(f"[Picsum] 随机封面 URL：{url}")
    return url


# ---------------------------------------------------------------------------
# AI 生成
# ---------------------------------------------------------------------------

def generate_ai(
    title: str,
    prompt: str,
    style: str,
    size: str,
    output_path: Path,
    ref_image: str | None = None,
    strength: float = 0.7,
    negative: str = "",
) -> bool:
    """Generate image using any OpenAI-compatible images API (DALL-E, Gemini Imagen, etc.)"""
    auth = load_image_auth()
    if auth is None:
        print("[AI] 图片生成配置不可用：未找到有效凭证")
        print("")
        print("请在 Agent 设置中填写：")
        print("  image_api_key   — 图片生成 API Key（支持 OpenAI / Gemini 等）")
        print("  image_base_url  — API 端点（OpenAI 留空；Gemini 填 https://generativelanguage.googleapis.com/v1beta/openai/）")
        return False

    base_url, credential, model, auth_type = auth
    if auth_type == "easyclaw" and ":" in credential:
        uid, token = credential.split(":", 1)
        client = build_openai_client(base_url, uid, token)
    else:
        client = OpenAI(api_key=credential, base_url=base_url)

    # Build enhanced prompt
    enhanced_prompt = prompt
    if style and style in STYLE_ENHANCEMENTS:
        enhanced_prompt = f"{STYLE_ENHANCEMENTS[style]}, {prompt}"
    enhanced_prompt = f"{enhanced_prompt}, {DEFAULT_QUALITY_SUFFIX}"

    # Safety check
    is_safe, matched = check_prompt_safety(enhanced_prompt)
    if not is_safe:
        print(f"[Safety] 提示词包含敏感内容（匹配词：{matched}），已拒绝生成")
        return False

    # Map size to standard API sizes
    aspect_ratio = size_to_aspect_ratio(size)
    size_map = {
        "16:9": "1792x1024", "9:16": "1024x1792",
        "4:3": "1792x1024", "3:4": "1024x1792",
        "1:1": "1024x1024", "3:2": "1792x1024", "2:3": "1024x1792",
    }
    api_size = size_map.get(aspect_ratio, "1792x1024")

    print(f"[AI] 调用 {model} — 文生图")
    print(f"[AI] Prompt: {enhanced_prompt[:120]}...")
    print(f"[AI] Size: {api_size}")

    try:
        response = client.images.generate(
            model=model,
            prompt=enhanced_prompt,
            n=1,
            size=api_size,
        )
    except Exception as e:
        print(f"[AI] API 调用失败：{e}")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if save_image_from_response(response, output_path):
        crop_to_aspect_ratio(output_path, aspect_ratio)
        print(f"[OK] 图片已保存：{output_path}")
        return True

    print("[AI] 响应中未包含图片数据")
    return False


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="封面图生成器（EasyClaw Seedream 5.0 Lite）"
    )
    parser.add_argument("--title", required=True, help="文章标题（必填）")
    parser.add_argument("--prompt", default="", help="自定义 AI 提示词（可选，覆盖自动生成的提示词）")
    parser.add_argument("--style", default="",
                        choices=[""] + sorted(set(STYLE_ENHANCEMENTS)),
                        help="风格预设（可选，增强封面视觉风格）")
    parser.add_argument("--size", default=DEFAULT_SIZE,
                        help=f"图片尺寸，格式 宽*高（默认 {DEFAULT_SIZE}）")
    parser.add_argument("-o", "--output", default=None,
                        help="输出路径（默认 output/covers/cover_时间戳.jpg）")
    parser.add_argument("--no-ai", action="store_true",
                        help="跳过 AI，直接使用 Picsum 随机图")
    parser.add_argument("--allow-fallback", action="store_true",
                        help="AI 失败时自动使用 Picsum 随机图（需用户明确授权）")
    parser.add_argument("--negative", default="",
                        help="额外的负面提示词（追加到默认负面词之后）")
    parser.add_argument("--image", default=None,
                        help="参考图片路径（启用图生图模式）")
    parser.add_argument("--strength", type=float, default=0.7,
                        help="图生图变换强度 0.0-1.0（默认 0.7，越大变化越大）")
    args = parser.parse_args()

    # 封面强制宽图（禁止竖图和方图）
    try:
        w, h = (int(x) for x in args.size.split("*"))
        if h >= w:
            print(f"[Warning] 封面图尺寸 {args.size} 不是宽图，自动转为默认封面尺寸 1280*720")
            args.size = "1280*720"
    except ValueError:
        pass

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"cover_{ts}.jpg"

    # 加载参考图（图生图模式）
    ref_image_data = None
    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            print(f"[Error] 参考图片不存在: {image_path}")
            sys.exit(1)
        if args.strength < 0.0 or args.strength > 1.0:
            print(f"[Error] --strength 必须在 0.0 到 1.0 之间，当前值: {args.strength}")
            sys.exit(1)
        try:
            ref_image_data = load_reference_image(image_path)
            print(f"[img2img] 已加载参考图: {image_path}")
        except (FileNotFoundError, ValueError) as e:
            print(f"[Error] {e}")
            sys.exit(1)

    public_url: str | None = None

    if args.no_ai:
        print("[Skip] 已指定 --no-ai，跳过 AI 生成，改用随机封面")
        public_url = fetch_picsum(args.size, output_path)
    else:
        # 尝试 AI 生成
        success = generate_ai(
            args.title, args.prompt, args.style, args.size, output_path,
            ref_image=ref_image_data, strength=args.strength,
            negative=args.negative,
        )

        if success:
            # AI 生成成功：上传到 transfer.sh 获取公开 URL
            public_url = upload_to_transfer_sh(output_path)
        else:
            # AI 失败：检查是否授权 fallback
            if args.allow_fallback:
                print("[Fallback] AI 生成失败，用户已授权使用随机封面...")
                public_url = fetch_picsum(args.size, output_path)
            else:
                print("[Error] AI 封面生成失败。如需使用随机封面，请使用 --allow-fallback 或 --no-ai 参数")
                sys.exit(2)

    if not public_url:
        print("[Error] 封面生成失败")
        sys.exit(1)

    print(f"[SHARE] ![{output_path.stem}]({public_url})")
    print(f"[LINK]  {public_url}")


if __name__ == "__main__":
    main()
