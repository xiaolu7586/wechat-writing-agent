# Cover Generator

Generate cover images for WeChat Official Account articles. Uses any OpenAI-compatible image API (DALL-E, Gemini Imagen, etc.). When AI fails, the script exits with code 2 (unless `--allow-fallback` is specified). The Agent should ask the user before retrying with fallback.

## ⚠️ CRITICAL OUTPUT RULE — READ THIS FIRST

After running the script, find the line starting with `[SHARE]` in stdout. Your reply MUST contain exactly that line — nothing else represents the image to the user.

**The only correct output format is:**
```
![cover_name](https://the-url-from-share-line)
```

**NEVER do any of these:**
- NEVER mention a local file path (e.g. `/root/.openclaw/.../cover.jpg`) to the user — local paths are invisible to users
- NEVER say "the cover has been generated" without showing the image inline
- NEVER replace the `[SHARE]` line with a text description or a plain URL
- NEVER omit the `![name](url)` format — without it the image will not render

If the `[SHARE]` line says "Upload failed" or contains a local path, the image is NOT deliverable. In that case, tell the user the upload failed and ask whether to retry.

## Configuration

Image generation credentials are loaded in priority order:

1. **`.secrets/image-config.json`** (recommended) — set via Agent settings form:
   - `image_api_key`: your API key (OpenAI, Gemini, or any compatible provider)
   - `image_base_url`: API endpoint URL (leave empty for OpenAI; for Gemini use `https://generativelanguage.googleapis.com/v1beta/openai/`)
2. **Environment variables**: `IMAGE_API_KEY`, `IMAGE_BASE_URL`
3. **Platform runtime** (`~/.easyclaw/`) — injected automatically on supported platforms

If no credentials are found, the script exits with code `2` and prints setup instructions. The agent should relay these to the user.

## Dependencies

```bash
pip install openai Pillow
```

## Content Safety

The script includes a built-in keyword filter that blocks prompts containing politically sensitive, pornographic, violent, gambling, drug-related, or discriminatory content. The Agent should also perform semantic-level safety judgment before calling the script — the keyword filter is a safety net, not the primary defense.

## Usage

```bash
# Basic usage (uses Seedream 5.0 Lite AI; exits with code 2 on failure)
python3 scripts/generate_cover.py --title "Article Title" -o cover.jpg

# Custom AI prompt
python3 scripts/generate_cover.py --title "Article Title" --prompt "Cyberpunk city night scene, blue-purple tones" -o cover.jpg

# Allow automatic fallback to Picsum (user has authorized)
python3 scripts/generate_cover.py --title "Article Title" --allow-fallback -o cover.jpg

# Skip AI and use Picsum random cover
python3 scripts/generate_cover.py --title "Article Title" --no-ai -o cover.jpg

# Specify dimensions
python3 scripts/generate_cover.py --title "Article Title" --size 1200*630 -o cover.jpg

# Image-to-image cover (图生图封面)
python3 scripts/generate_cover.py --title "Article Title" \
  --image /path/to/reference.jpg -o cover.jpg

# img2img with custom strength
python3 scripts/generate_cover.py --title "Article Title" \
  --image /path/to/reference.jpg --strength 0.5 -o cover.jpg
```

## Parameters

| Parameter | Description | Default |
|---|---|---|
| `--title` | Article title (required) | - |
| `--prompt` | Custom AI prompt | Auto-generated based on title |
| `--size` | Image dimensions (width*height), internally converted to aspect ratio | `1280*720` |
| `-o` | Output path | `output/covers/cover_timestamp.jpg` |
| `--no-ai` | Skip AI and use Picsum random cover directly | false |
| `--allow-fallback` | AI 失败时自动使用 Picsum 随机图（需用户明确授权） | false |
| `--image` | Reference image path (enables img2img mode). Supports PNG/JPG/WebP, max 10 MB | - |
| `--strength` | img2img transformation strength 0.0-1.0 (higher = more change) | `0.7` |

## 封面 Prompt 构造指南

封面图的核心目标是在信息流中吸引点击，同时传达文章调性。与文章插图不同，封面更注重视觉冲击力和信息概括性。

**构造原则：**
1. **一眼传达主题** — 封面要让读者在信息流中快速理解文章讲什么
2. **视觉冲击优先** — 封面比插图更需要吸引力，对比度和色彩饱和度可以适当提高
3. **简洁大气** — 封面画面不宜过于复杂，1 个主体 + 干净背景即可
4. **无文字** — 微信会自动叠加标题，封面图本身不应包含文字

**风格选择建议：**

| 文章类型 | 推荐风格思路 | 示例 prompt 方向 |
|---------|------------|----------------|
| 科技/AI | 未来感、深色背景、光效 | dark futuristic, neon accents, tech visualization |
| 财经/商业 | 专业、克制、几何感 | professional, geometric, navy-gold palette |
| 生活方式 | 温暖、自然光、生活场景 | warm lifestyle, natural light, cozy atmosphere |
| 情感/故事 | 电影感、叙事氛围 | cinematic, storytelling mood, dramatic lighting |
| 教育/知识 | 明快、友好、清晰 | bright, friendly, clean educational style |
| 通用 | 杂志编辑风 | editorial photography, clean composition |

**自定义 prompt 时的注意事项：**
- 使用 `--prompt` 参数覆盖默认的基于标题自动生成的 prompt
- prompt 用英文效果更好
- 脚本会自动追加质量后缀和负面词，无需手动添加 "no text, no watermark"
- 封面尺寸固定为横图（`1280*720` 或 `1200*630`），不支持竖图

**安全规则：** 封面 prompt 同样适用生图提示词安全规则（政治、色情、暴力、赌博、毒品、宗教、真人肖像、歧视、儿童安全等均禁止）。详见 image-generator SKILL.md 的 Content Safety 章节。

## Generation Logic

```
API key configured? (secrets / env / platform runtime)
    ├── Yes → --image provided?
    │           ├── Yes → Call API (img2img mode) → Success → Save + upload to transfer.sh (exit 0)
    │           │                                 → Failure → --allow-fallback?
    │           │                                               ├── Yes → Fetch Picsum (exit 0/1)
    │           │                                               └── No → exit 2 (Agent asks user)
    │           └── No → Call API (txt2img mode) → Success → Save + upload to transfer.sh (exit 0)
    │                                            → Failure → --allow-fallback?
    │                                                          ├── Yes → Fetch Picsum (exit 0/1)
    │                                                          └── No → exit 2 (Agent asks user)
    └── No → --allow-fallback?
              ├── Yes → Fetch Picsum (exit 0/1)
              └── No → exit 2 (Agent asks user)
```

On success, the script prints:
```
[SHARE] ![cover_20240101_120000](https://transfer.sh/xxx/cover_20240101_120000.jpg)
[LINK]  https://transfer.sh/xxx/cover_20240101_120000.jpg
```

**Agent output instruction:** When the script succeeds, find the `[SHARE]` line in stdout and copy it verbatim into your reply — this renders as an inline image in the chat UI:
```
![cover_20240101_120000](https://transfer.sh/xxx/cover_20240101_120000.jpg)
```
Do NOT omit this line. Do NOT replace it with a text link.

**On failure (exit code 1 or 2):** Report the exact error message from stdout to the user. Do NOT claim the cover was generated locally or by any other means. Ask the user whether to use a random placeholder cover (`--allow-fallback`) or fix the API key first.

**Exit codes:** `0` = success, `1` = complete failure, `2` = AI failed but fallback not authorized.

`--no-ai` always skips AI and fetches a random image from Picsum Photos.

## Integration with Other Skills

After generating a cover, specify it when publishing via `publish-orchestrator`:

```bash
npx -y bun skills/publish-orchestrator/scripts/wechat-api.ts article.md \
  --cover cover.jpg
```


