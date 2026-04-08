---
name: daily-trending
description: Fetch today's trending topics from tophub.today across multiple platforms. Triggered when users ask "what's trending today", "hot topics", or "Weibo trending".
---

# Daily Trending

Fetch today's trending topics by scraping data from various platforms via tophub.today.

## Data Collection

### Multi-Platform Trending Lists (Required)

Fetch trending lists from the following platforms on tophub.today:
- Zhihu Hot List: `/n/mproPpoq6O`
- Weibo Trending: `/n/KqndgxeLl9`
- Baidu Real-time Hot Topics: `/n/Jb0vmloB1G`
- 36Kr 24-Hour Hot List: `/n/Q1Vd5Ko85R`
- Huxiu Hot Articles: `/n/5VaobgvAj1`
- The Paper Hot List: `/n/wWmoO5Rd4E`
- 52pojie Today's Hot Posts: `/n/NKGoRAzel6`
- Hupu Community Hot Posts: `/n/G47o8weMmN`

### Fetching Strategy

**⚠️ Important: Always use `web_fetch` to retrieve tophub.today pages. Do NOT use `web_search` — search engines do not index real-time trending lists and will return stale results.**

**Always fetch all 3 core platforms — do not stop early even if one platform yields enough items:**
```bash
web_fetch("https://tophub.today/n/KqndgxeLl9", maxChars=5000)  # Weibo
web_fetch("https://tophub.today/n/mproPpoq6O", maxChars=5000)  # Zhihu
web_fetch("https://tophub.today/n/Jb0vmloB1G", maxChars=5000)  # Baidu
```

**Fetching Strategy:**
1. Fetch all 3 platforms every time — Weibo, Zhihu, Baidu in order
2. From each platform extract the top 5 items independently
3. Merge all 15 candidates, deduplicate overlapping topics, then select the 5 most newsworthy for the final output
4. If one platform fetch fails, continue with the remaining two and note it
5. If `web_fetch` returns an error or no trending items are visible on any platform, tell the user "热点数据暂时获取失败，请稍后重试" — do NOT fall back to `web_search` or use training data to invent trending topics

### Filtering Criteria (Critical)

From all platform trending lists, filter out **truly important topics that are genuinely at the center of discussion**:

1. **Major Events**: Significant policies, international relations, social events
2. **Hot Discussion Topics**: Topics that spark widespread discussion and debate
3. **True Focus Points**: Not celebrity gossip or promotional content
4. **Facts Only**: Exclude subjective commentary headlines like "sky is falling", "worst ever", "absurd", etc.
5. **Factual Content**: Keep the events themselves without added commentary or sensationalism

**Exclude:**
- Headlines with subjective commentary
- Pure entertainment gossip
- Obvious promotional content
- Emotional expressions

**Include:**
- Factual events
- Policy updates
- Socially debated topics
- Truly discussion-worthy focal points

**Output Requirements:**
- Each news item must be complete with clear beginning and end
- Describe events like news headlines
- Avoid single words or incomplete fragments

## Output Format

Output only the 5 most valuable items:

```
---

🔥 Today's Trending (February 19)

1. Sanae Takaichi confirmed as Japan's new Prime Minister, to form new cabinet
2. 2026 Spring Festival box office surpasses 2 billion yuan
3. Su Yiming wins gold in men's slopestyle snowboarding at Milan Winter Olympics
4. South Korea wins gold in women's 3000m short track speed skating relay
5. Saudi Arabia invests $48.3 billion to acquire part of ByteDance business

---
```

Notes:
- Each news item should be complete with clear beginning and end
- No source attribution needed
- Facts only, exclude subjective commentary
- Replace divider "---" with "======"
- Output only the required content, no extra text, explanations, or error messages before or after

