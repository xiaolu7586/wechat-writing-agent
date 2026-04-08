---
name: image-generator
description: |
  Generate images for WeChat articles using any OpenAI-compatible image API
  (DALL-E, Gemini Imagen, etc.). This skill provides the image-generation
  primitive used after the agent decides whether inline images are needed.
  Called by article-writer after article completion. Supports multiple sizes and
  styles for different use cases. Also supports image-to-image (img2img / 图生图) mode.
---

# Image Generator

Generate inline images for WeChat Official Account articles. Supports any OpenAI-compatible image generation API. If no API key is configured, the script reports failure and exits.

## ⚠️ CRITICAL OUTPUT RULE — READ THIS FIRST

After running the script, find the line starting with `[SHARE]` in stdout. Your reply MUST contain exactly that line — nothing else represents the image to the user.

**The only correct output format is:**
```
![image_name](https://the-url-from-share-line)
```

**NEVER do any of these:**
- NEVER mention a local file path (e.g. `/root/.openclaw/.../image.jpg`) to the user — local paths are invisible to users
- NEVER say "the image has been generated" without showing it inline
- NEVER replace the `[SHARE]` line with a text description or a plain URL
- NEVER omit the `![name](url)` format — without it the image will not render

If the `[SHARE]` line says "Upload failed" or contains a local path, the image is NOT deliverable. In that case, tell the user the upload failed and ask whether to retry.

This skill does **not** decide by itself whether an article should have images. The agent must make that decision first, then call `generate_image.py` for each approved image.

## Use Cases

- Triggered by article-writer after it decides inline images are needed
- User explicitly requests "add images to this article"
- Generate specific image with custom prompt
- 用户说"图生图" — 基于参考图变换生成新图片

## 视觉内容总监角色

进入配图插画环节时，Agent 自动激活此角色。

你现在是一位资深视觉内容总监，同时精通内容策略和视觉设计。你的核心职责不是"给文章配一张好看的图"，而是"将文章的核心概念翻译为视觉语言"。

**能力一：内容理解（先读懂，再动手）**
- 精读插图位置前后 2-3 段文字，提取该段落的**核心概念**（不是泛主题，是具体论点）
- 识别段落的**情绪状态**（焦虑、兴奋、反思、启发、冲突、和解...）
- 找到**可视化锚点**——段落中最适合转化为画面的那个意象、比喻或场景
  - 例：文章讲"AI 正在蚕食传统岗位" → 可视化锚点可以是"旧工具在新光线下逐渐透明"
  - 例：文章讲"理财的核心是延迟满足" → 可视化锚点可以是"种子在泥土下缓慢发芽的剖面"
  - 例：文章讲"独居年轻人的周末仪式感" → 可视化锚点可以是"窗边一杯咖啡和摊开的书"

**能力二：视觉翻译（概念→画面）**
- 将可视化锚点转化为具体场景描述，而非抽象概念堆叠
- 每张图只表达一个视觉主题，大量留白，主体突出
- 同一篇文章的所有配图共享视觉风格系统（色调、光影、质感一致）
- 根据公众号领域选择对应的视觉基调（见下方映射表）
- 拒绝"通用素材图"——不要生成"一个人在用电脑"这种毫无特色的画面
- 图片内不放任何文字、标题、水印

**内容→视觉翻译的反面教材（禁止）：**
- 文章讲 AI → 配图"一个机器人" — 太泛，没有传达文章的具体观点
- 文章讲理财 → 配图"一堆金币" — 太直白，像素材库搜出来的
- 文章讲健康 → 配图"一个人在跑步" — 通用素材图，和文章具体内容无关

**正确做法：**
- 文章讲"AI 替代重复劳动" → 配图"空荡的传统工位上方悬浮着一束数据光流，warm/cool 交界"
- 文章讲"长期投资的复利效应" → 配图"微距拍摄：一枚硬币上长出嫩芽，旁边是年轮般的同心圆光影"
- 文章讲"秋季养生茶" → 配图"木质茶桌上的玻璃壶，金色茶汤折射窗外秋叶光斑"

## 领域→视觉基调映射

从 config/config.json 的 account.field 或 memory/domain.txt 读取领域：

| 领域 | 推荐 --style | 视觉基调 | 色调倾向 | 避免 |
|------|-------------|---------|---------|------|
| 科技/AI | `tech` | 未来感、精密、冷峻 | 深蓝-紫-银色系 | 暖色调、手绘风 |
| 财经/商业 | `finance` | 权威、专业、克制 | 深蓝-灰-金色系 | 过于鲜艳、可爱风 |
| 生活方式 | `lifestyle` | 温暖、自然、舒适 | 奶油-米白-鼠尾草绿 | 冷硬科技感 |
| 教育/知识 | `education` | 清晰、友好、明快 | 浅蓝-暖黄-白色系 | 暗黑风、过于抽象 |
| 情感/故事 | `cinematic` | 电影感、叙事、沉浸 | 青橙对比、暖金 | 平面设计风 |
| 时尚/美妆 | `editorial` | 杂志感、高级、精致 | 莫兰迪低饱和色系 | 素材图感、过于工整 |
| 通用/未指定 | `editorial` | 杂志编辑风、干净大气 | 低饱和中性色 | 极端风格 |

这是指引而非死规则。Agent 根据具体文章内容灵活调整。

## Prompt 构造五步法

**第一步 — 读文提概念**：精读插图位置的段落，用一句话概括"这段讲的核心是什么"，找到可视化锚点

**第二步 — 定情绪基调**：确定这张图的情绪关键词（1-2 个词），并根据领域映射表选择 --style 参数

**第三步 — 场景化翻译**：将可视化锚点转化为具体的场景描述（而非抽象概念词），按 8 维度逐一填充：
- 风格词在最前面（定整体调性）
- 场景和主体在中间（定画面内容——这是和文章关联的核心部分）
- 光影和色彩在最后（定氛围）

**第四步 — 追加控制词**：
- 脚本会自动追加质量后缀（no text, no watermark 等）和默认负面词，无需手动添加
- 如需额外排除特定元素，通过 --negative 参数传入

**第五步 — 一致性检查**：
- 这张图能让读者"看到文章在讲什么"吗？（内容相关性）
- 色调与段落情绪一致吗？（情绪匹配）
- 与同篇文章其他图的风格统一吗？（系列感）

## 8-Dimension Visual Framework

Agent must analyze and specify ALL 8 dimensions before calling the script:

| 维度 | 说明 | 示例 |
|------|------|------|
| 风格/媒介 | 整体视觉风格或创作媒介 | 极简主义设计、胶片摄影、3D Render、水彩插画、扁平设计 |
| 构图 | 画面布局和视觉引导 | 中心对称、三分法、L形布局、对角线构图、鸟瞰俯拍 |
| 空间环境 | 场景背景的材质、反光、结构 | 磨砂玻璃办公室、暖木质书房、工业水泥墙、户外草坪 |
| 主体 | 画面主角的材质、结构、边缘处理 | 模糊人物剪影、精致机械结构、柔和边缘手绘人物 |
| 细节 | 文字内容、字体、纹理等微观元素 | 无文字水印、亚麻纹理背景、像素网格细节 |
| 光影 | 光源方向、反射、氛围光 | 左侧45度暖光、逆光剪影、丁达尔效应、柔和漫反射 |
| 色彩 | 色调倾向和主色调 | 莫兰迪低饱和、冷蓝灰主调 #4A6FA5、暖橙渐变 |
| 镜头 | 焦段和景深效果 | 35mm广角、85mm人像虚化、微距特写、移轴效果 |

**8 维度精选词库（供选取组合，不需要每个词都用）：**

**风格/媒介：** editorial photography, cinematic film still, fine art photography, soft focus lifestyle, macro detail shot, aerial top-down, oil painting texture, watercolor wash, digital illustration flat design, isometric 3D render, minimalist graphic, documentary style

**构图：** rule-of-thirds, centered symmetrical, diagonal dynamic, leading lines, frame within frame, negative space dominant, bird's-eye overhead, low angle heroic, golden ratio spiral, layered depth

**空间环境：** soft studio backdrop gradient, natural outdoor golden hour, modern office glass walls, cozy home warm wood, industrial concrete raw texture, abstract geometric space, misty atmospheric, clean white infinity, urban cityscape bokeh

**主体：** abstract silhouette soft edges, floating geometric objects, detailed mechanical precision, organic natural forms, conceptual metaphor visualization, blurred anonymous figure, product hero shot, landscape panorama, still life arrangement

**细节：** subtle film grain, linen texture, glass reflection, water droplets, metallic sheen, paper texture overlay, light dust particles, fabric folds

**光影：** soft diffused studio, golden hour directional warm, rim light silhouette, Rembrandt dramatic side, flat even ambient, neon accent glow, backlit halo, window light with curtain diffusion

**色彩：** muted desaturated Morandi palette, teal-and-orange cinematic, monochrome with single accent color, warm earth tones, cool blue-gray professional, pastel soft dreamy, deep navy-gold luxurious, sage-cream-terracotta natural

**镜头：** 85mm portrait shallow DOF bokeh, 35mm wide environmental, 50mm standard natural perspective, 100mm macro detail, 24mm ultra-wide dramatic, tilt-shift miniature effect

**Prompt 组装规则：**
- 按 8 维度依次描述，确保每个维度都有值
- 核心描述词建议用英文以获得更好效果
- 脚本自动追加质量后缀和负面词，prompt 中**无需手动写** "no text, no watermark"
- 与文章情绪弧线保持一致（焦虑段用冷色调，希望段用暖色调）

## 高质量 Prompt 范例

展示从内容到 prompt 的完整推导，供 Agent 学习思路：

**范例 1 — 科技文章段落："AI Agent 正在改变软件开发的范式"**
- 可视化锚点：不是"一个机器人写代码"，而是"代码在空间中自动编织成网络结构"
- 情绪：前沿、精密、有秩序的变革感
```bash
python3 ${SKILL_DIR}/scripts/generate_image.py \
  --prompt "futuristic technology visualization, dynamic diagonal composition, \
dark matte background with subtle hexagonal grid pattern, \
luminous code fragments assembling themselves into an intricate neural network structure, \
holographic translucent nodes with data flowing through connecting threads, \
cool neon blue accent lighting from below with deep purple ambient fill, \
deep navy #1a1a2e base with electric blue #00d4ff and violet #7c3aed accents, \
wide angle 24mm lens deep perspective vanishing point" \
  --style "tech" --size "1280*720" \
  --negative "cartoon, childish, robot, warm tones, cluttered, human figure" \
  -o drafts/images/img_001.jpg
```

**范例 2 — 生活方式段落："独居的周末，从一杯手冲咖啡开始"**
- 可视化锚点：不是"一杯咖啡"，而是"晨光、手冲壶、蒸汽、一个人的安静仪式"
- 情绪：温暖、安静、仪式感
```bash
python3 ${SKILL_DIR}/scripts/generate_image.py \
  --prompt "natural lifestyle editorial photography, relaxed off-center composition, \
cozy kitchen corner with warm wood countertop and morning light, \
hand-pour coffee dripper with rising steam catching sunlight, \
open book and ceramic cup on linen cloth nearby, \
warm golden daylight streaming through sheer curtains with soft shadows, \
cream #F5F0EB and sage green #9CAF88 and warm honey #D4A574 palette, \
35mm wide angle slight vignette natural perspective" \
  --style "lifestyle" --size "1280*720" \
  -o drafts/images/img_002.jpg
```

**范例 3 — 财经段落："复利效应需要时间，大多数人倒在黎明前"**
- 可视化锚点：不是"金币堆"，而是"黑暗中一棵嫩芽正在突破硬币堆"——寓意坚持和生长
- 情绪：克制、希望、力量感
```bash
python3 ${SKILL_DIR}/scripts/generate_image.py \
  --prompt "professional fine art still life photography, centered composition generous negative space, \
dark textured surface with scattered old coins, \
single green sprout breaking through the coin pile reaching toward soft overhead light, \
dramatic Rembrandt side lighting with warm accent from above, \
deep charcoal #2C2C2C base with muted gold #B8964E and fresh green #6B8E5A accent, \
100mm macro lens shallow depth of field with beautiful bokeh" \
  --style "finance" --size "1280*720" \
  --negative "bright, colorful, cartoon, person, stock photo" \
  -o drafts/images/img_003.jpg
```

**范例 4 — 情感故事段落："她决定不再回头看那座城市"**
- 可视化锚点：不是"一个女人"，而是"雨后街道上一个模糊背影渐行渐远"——叙事张力
- 情绪：释然、淡淡的忧伤、向前
```bash
python3 ${SKILL_DIR}/scripts/generate_image.py \
  --prompt "cinematic film still, wide anamorphic composition with letterbox feel, \
quiet city street after rain with reflective wet pavement and scattered fallen leaves, \
lone figure walking away silhouette with umbrella softly blurred edges, \
golden hour warm backlight from behind with cool blue ambient shadows, \
teal #2C6E6A shadows transitioning to warm amber #E8A87C highlights, \
50mm prime lens natural perspective beautiful circular bokeh" \
  --style "cinematic" --size "1280*720" \
  -o drafts/images/img_004.jpg
```

## Script Directory

This skill's scripts are located in `${SKILL_DIR}/scripts/`, where `SKILL_DIR` is the directory containing this SKILL.md file.

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/generate_image.py` | Generate single image | `python3 ${SKILL_DIR}/scripts/generate_image.py --prompt "描述" -o output.jpg` |

## Configuration

Image generation credentials are loaded in priority order:

1. **`.secrets/image-config.json`** (recommended) — set via Agent settings form:
   - `image_api_key`: your API key (OpenAI, Gemini, or any compatible provider)
   - `image_base_url`: API endpoint URL (leave empty for OpenAI; for Gemini use `https://generativelanguage.googleapis.com/v1beta/openai/`)
2. **Environment variables**: `IMAGE_API_KEY`, `IMAGE_BASE_URL`
3. **Platform runtime** (`~/.easyclaw/`) — injected automatically on supported platforms

**Model auto-detection:** if `image_base_url` contains `googleapis.com`, the model is automatically set to `imagen-3.0-generate-001`; otherwise defaults to `dall-e-3`.

If no credentials are found, the script prints setup instructions and exits with code `1`.

## Dependencies

```bash
pip install openai Pillow
```

## Image Sizes

| Size | Use Case | Aspect Ratio |
|------|----------|--------------|
| `1280*720` | Default inline image | 16:9 landscape |
| `600*800` | Portrait image (**不推荐用于文章插图**) | 3:4 portrait |
| `1280*720` | Cover image (delegates to cover-generator) | 16:9 landscape |

Note: `--size` is specified in `宽*高` format but internally converted to an aspect ratio for the Seedream 5.0 Lite model.

**文章插图始终使用横图方向。** 脚本会自动将竖图（如 `600*800`）和方图（如 `800*800`）转为默认宽图尺寸。

## Workflow

### Mode 1: Agent-Orchestrated Inline Images (Recommended)

After article writing, the **agent must first make an image decision**, then use this skill to generate the approved images.

**Decision protocol:**

1. Analyze article theme, emotional tone, and structure
2. Decide image count and positions based on content needs
3. Choose one of two outcomes:
   - **Generate images** and insert them into Markdown
   - **Skip images** and explicitly state the reason
4. If generating, follow the **Prompt 构造五步法** above to construct each prompt, then:
   - Create the images directory
   - Call `generate_image.py` once per image
   - Insert `![](./images/img_001.jpg)` into Markdown
5. If skipping:
   - Record the exact reason in the work summary

**Default guidance:**
- News brief / very short article: 0-1 image
- Standard article: usually 1-3 images
- Deep analysis article: usually 2-5 images
- For non-news articles, default to at least 1 image unless there is a clear skip reason

### Mode 2: Single Image Generation

Generate a specific image with custom prompt:

```bash
# Basic usage
python3 ${SKILL_DIR}/scripts/generate_image.py --prompt "AI assistant working on laptop" -o image.jpg

# With custom size
python3 ${SKILL_DIR}/scripts/generate_image.py --prompt "Data visualization chart" --size 1280*720 -o chart.jpg

# With style hint
python3 ${SKILL_DIR}/scripts/generate_image.py --prompt "Tech startup office" --style tech -o office.jpg

# Skip generation
python3 ${SKILL_DIR}/scripts/generate_image.py --prompt "anything" --no-ai -o image.jpg
```

### Mode 3: Image-to-Image Generation (图生图)

Transform an existing image based on a text prompt. The reference image provides structure and composition, while the prompt controls the style and content changes.

```bash
# Basic img2img — convert to watercolor style
python3 ${SKILL_DIR}/scripts/generate_image.py \
  --prompt "转换为水彩画风格，保持原有构图" \
  --image /path/to/reference.jpg \
  -o output_img2img.jpg

# With custom strength (lower = closer to reference)
python3 ${SKILL_DIR}/scripts/generate_image.py \
  --prompt "赛博朋克风格重绘" \
  --image /path/to/reference.jpg \
  --strength 0.5 \
  -o output_cyberpunk.jpg
```

**Strength reference:**

| Strength | Effect | Use Case |
|----------|--------|----------|
| `0.1-0.3` | Very close to original, subtle changes | Minor color/style adjustments |
| `0.4-0.6` | Moderate transformation, preserves structure | Style transfer, mood change |
| `0.7` (default) | Significant transformation, general layout kept | Creative re-imagining |
| `0.8-1.0` | Major changes, loose reference only | Radical style change |

**Supported formats:** PNG, JPG/JPEG, WebP (max 10 MB)

## Parameters

### generate_image.py

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--prompt` | Image description (required for AI mode) | - |
| `--size` | Image dimensions (width*height), internally converted to aspect ratio | `1280*720` |
| `--style` | Style preset (see table below) | `modern` |
| `-o, --output` | Output path | `output/images/img_timestamp.jpg` |
| `--no-ai` | Skip image generation and do not output a file | false |
| `--negative` | Extra negative prompt keywords (appended to built-in negative prompt) | `""` |
| `--context` | Article context for better prompt generation | - |
| `--image` | Reference image path (enables img2img mode). Supports PNG/JPG/WebP, max 10 MB | - |
| `--strength` | img2img transformation strength 0.0-1.0 (higher = more change) | `0.7` |

## Style Presets

Each `--style` prepends a full visual recipe (lighting, composition, color, lens) before your prompt, defining the overall tone. The script also auto-appends a quality suffix ("no text, no watermark, high quality, 4K detail") and a default negative prompt to every generation.

| Style | Visual Direction | Best For |
|-------|-----------------|----------|
| `modern` | Editorial magazine photography, soft studio lighting, film grain (alias of `editorial`) | General articles |
| `editorial` | Same as modern — magazine-quality, rule-of-thirds, muted tones | Fashion, design |
| `cinematic` | Film still, anamorphic, golden hour, teal-orange grading | Storytelling, emotion |
| `minimal` | Ultra-minimalist flat design, 2-3 color palette, whitespace | Clean concepts |
| `warm` | Lifestyle photography, window light, earth tones, cozy | Life, food, wellness |
| `tech` | Futuristic, neon blue-purple accents, chrome surfaces, dark background | Tech, AI, digital |
| `bold` | High-impact graphic, chiaroscuro hard light, saturated primaries | Opinion, impact |
| `finance` | Professional business, symmetric, navy-gray-gold, glass/marble | Finance, business |
| `lifestyle` | Natural daylight, pastel earth palette, airy casual | Lifestyle, daily |
| `education` | Bright, structured, cheerful warm colors, rounded shapes | Education, tutorial |

**How style affects output:**
```
--prompt "coffee shop interior" --style warm
→ Actual prompt: "warm lifestyle photography, natural window light golden tones, ... coffee shop interior, no text, no watermark, ..."
```

The style recipe is prepended (not appended) so it defines the base visual tone, while your prompt supplies the specific content.

**Choosing a style:** Refer to the **领域→视觉基调映射** section below. When unsure, `editorial` (the default) is a safe choice for most article types.

## Negative Prompts

The script automatically applies a default negative prompt to reduce low-quality artifacts:
- text, watermark, signature, letters, words, label, caption
- ugly, blurry, low quality, low resolution, pixelated
- oversaturated, cluttered, busy, messy, multiple borders, frames

Use `--negative` to add **extra** exclusions specific to your image:
```bash
--negative "cartoon, childish, robot, human figure"
```

These are appended to the default negative prompt (not replacing it).

## Content Safety

The script includes a built-in keyword filter that blocks prompts containing politically sensitive, pornographic, violent, gambling, drug-related, or discriminatory content. The Agent should also perform semantic-level safety judgment before calling the script — the keyword filter is a safety net, not the primary defense.

If a prompt is blocked, the script prints `[Safety] 提示词包含敏感内容` and exits without generating an image.

## Output

### generate_image.py Output

```
[AI] 调用 dall-e-3 — 文生图
[AI] Prompt: ...
[AI] Size: 1792x1024
[OK] 图片已保存：/path/to/image.jpg
[SHARE] ![img_001](https://transfer.sh/xxx/img_001.jpg)
[LINK]  https://transfer.sh/xxx/img_001.jpg
```

**Agent output instruction:** When the script succeeds, find the `[SHARE]` line in stdout and copy it verbatim into your reply — this renders as an inline image in the chat UI:
```
![img_001](https://transfer.sh/xxx/img_001.jpg)
```
Do NOT omit this line. Do NOT replace it with a text link.

**On failure (exit code 1):** Report the exact error message from stdout to the user. Do NOT claim the image was generated locally or by any other means. Do NOT produce placeholder or invented images.

### img2img Output

```
[img2img] 已加载参考图: /path/to/reference.jpg
[AI] 调用 dall-e-3 — 文生图
[AI] Prompt: 转换为水彩画风格，保持原有构图...
[AI] Size: 1792x1024
[OK] 图片已保存：/path/to/output.jpg
[SHARE] ![output_img2img](https://transfer.sh/xxx/output_img2img.jpg)
[LINK]  https://transfer.sh/xxx/output_img2img.jpg
```

### Example Agent-Orchestrated Output

```
[决策] 文章评估完成，计划插入 3 张插图
[位置] 第 2 段后 (字符 456)
[位置] 第 4 段后 (字符 1234)
[位置] 第 6 段后 (字符 2100)

[生成] 图片 1/3：AI工具界面示意图
[OK] 保存至 images/img_001.jpg
[插入] ![](./images/img_001.jpg)

[生成] 图片 2/3：数据可视化图表
[OK] 保存至 images/img_002.jpg
[插入] ![](./images/img_002.jpg)

[生成] 图片 3/3：团队协作场景
[OK] 保存至 images/img_003.jpg
[插入] ![](./images/img_003.jpg)

[完成] 插图决策已执行，共插入 3 张插图
```

## Skip / Failure Behavior

### When Image Generation Is Not Configured

```
[AI] 图片生成配置不可用：未找到有效凭证

请在 Agent 设置中填写：
  image_api_key   — 图片生成 API Key（支持 OpenAI / Gemini 等）
  image_base_url  — API 端点（OpenAI 留空；Gemini 填 https://generativelanguage.googleapis.com/v1beta/openai/）
[Error] 图片生成失败
```

The script exits with code `1`. The agent should relay the setup instructions to the user and ask them to configure their API key in Agent settings.

### When `--no-ai` Is Specified

```
[Skip] 已指定 --no-ai，跳过插图生成
```

The script exits with code `0` and does not create an image file. The caller should treat this as a recorded skip, not as a successful image insertion.

### When API Fails

```
[AI] API 调用失败：timeout
[Error] 图片生成失败
```

The script exits with code `1` and does not fall back to a placeholder image.

## Integration with Other Skills

- **article-writer**: Makes image decisions in Step 8, then calls `generate_image.py` for each approved image
- **cover-generator**: Delegates cover generation (1280*720 size)
- **publish-orchestrator**: Uploads inline images to WeChat and replaces local paths with media URLs

## Example Usage in article-writer

After article completion and image decision:

```bash
# Step 8: Decide images first
echo "[Step 8] 执行插图决策..."

# Create images directory
mkdir -p "$(dirname "$ARTICLE_PATH")/images"

# Generate one approved image
python3 ${SKILL_DIR}/scripts/generate_image.py \
  --prompt "YOUR DETAILED PROMPT HERE" \
  --style "modern" \
  --size "1280*720" \
  -o "$(dirname "$ARTICLE_PATH")/images/img_001.jpg"

# Output
echo "[完成] 插图决策已执行；如生成成功则已插入图片"
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `图片生成配置不可用` | No API key found | Set `image_api_key` in Agent settings (supports OpenAI, Gemini, etc.) |
| `openai not found` | Package not installed | `pip install openai` |
| No output image generated | `--no-ai` specified or image generation unavailable | Check logs to confirm whether generation was intentionally skipped |
| `API 调用失败` | Network or API error | Check network connectivity and image generation service status |
| `Image too dark/bright` | Prompt issue | Add lighting hints to prompt |
| `Image irrelevant` | Prompt too vague | Add more context via `--context` |
| `参考图片不存在` | `--image` path is wrong | Verify the file path exists |
| `参考图片过大` | Reference image exceeds 10 MB | Compress or resize the image before using |


