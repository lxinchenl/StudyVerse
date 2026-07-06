# Vision Provider Setup Guide

当主模型不支持图片输入时，使用此配置启用多模态图片理解。

## 方案选型

| 方案 | 适用场景 | 依赖 | 成本 |
|------|---------|------|------|
| PaddleOCR | 含文字的图（公式、代码、文字截图） | `paddleocr` + `paddlepaddle` | 无（本地） |
| Doubao API | 流程图、架构图需要结构理解 | `DOUBAO_API_KEY` env var | API token |
| Hermes auxiliary.vision | 内置 vision_analyze 工具 | 支持视觉的 provider | 按 provider 计费 |

## 方案一：PaddleOCR（推荐首选）

### 安装

```bash
pip install paddleocr paddlepaddle
```

### 使用

```python
from paddleocr import PaddleOCR
import warnings
warnings.filterwarnings('ignore')

ocr = PaddleOCR(lang='ch')
result = ocr.ocr(image_path)
if result and result[0]:
    text = '\n'.join(line[1][0] for line in result[0])
```

### 已知问题

- **paddlepaddle 3.x 不兼容**：安装 paddlepaddle 最新版（3.3+）后，PaddleOCR 可能报 `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support`。这是 PIR 执行引擎的兼容性问题。解决方案：
  - 降级到 paddlepaddle 2.6：`pip install paddlepaddle==2.6.0`
  - 或使用方案二（Doubao API）作为替代
- **首次运行会下载模型文件**（~几百 MB），后续使用有缓存

### 图片选择策略

不要对 `page.get_images()` 提取出的所有图都跑 OCR。先用尺寸过滤：

- `< 5KB`：直接跳过（页码、图标、装饰点）
- `5-50KB`：文字截图/公式截图，OCR 效果最好
- `> 50KB`：流程图/架构图/大图，OCR 可提取节点文字，但结构关系需要用 vision（走方案二）

## 方案二：豆包（Doubao / Volcengine）

### 所需信息

| 项目 | 值 |
|------|-----|
| API Key | `ark-43298c6d-41b5-4a04-bce0-b2c6ae918f2c-fed82` |
| Base URL | `https://ark.cn-beijing.volces.com/api/v3` |
| 模型 | `doubao-seed-2-0-mini-260428` |

### 设置

```bash
export DOUBAO_API_KEY="ark-43298c6d-41b5-4a04-bce0-b2c6ae918f2c-fed82"
```

### 使用

```bash
# 单张图片
python3 scripts/vision_analyze_doubao.py <image_path>

# 批量处理过程文件
python3 scripts/batch_vision.py <process_file.md>
```

## 方案三：Hermes auxiliary.vision

如果想用内置 `vision_analyze` 工具（而不是独立脚本），需配置：

```bash
hermes config set auxiliary.vision.provider openrouter
hermes config set auxiliary.vision.model openai/gpt-4o-mini
hermes config set auxiliary.vision.api_key <your-key>
```

## 回退方案

如果没有任何视觉/OCR 能力可用：
1. **仅用 pymupdf 文字**：`page.get_text()` 提取的文字通常已覆盖 80%+ 内容
2. **对于文字稀疏的页**（仅标题+页码<30字），通过上下文自行推断图中可能的流程和结构
3. **在最终笔记中用【注】标记**缺少的图信息，用户可自行补充

| 项目 | 值 |
|------|-----|
| API Key | |
| Base URL | `https://ark.cn-beijing.volces.com/api/v3` |
| 模型 | `doubao-seed-2-0-mini-260428` |

### 设置方法

```bash
export DOUBAO_API_KEY=
```

或者写入 `~/.bashrc` 持久化：

```bash
echo 'export DOUBAO_API_KEY=' >> ~/.bashrc
```

### 使用方式

```bash
# 单张图片
python3 scripts/vision_analyze_doubao.py <image_path>

# 批量处理过程文件
python3 scripts/batch_vision.py <process_file.md>
```

## 选项二：配置 Hermes auxiliary.vision

如果后续想用 Hermes 内置的 `vision_analyze` 工具（而不是独立脚本），需要配置 auxiliary vision provider：

```bash
hermes config set auxiliary.vision.provider openrouter
hermes config set auxiliary.vision.model openai/gpt-4o-mini
hermes config set auxiliary.vision.base_url https://openrouter.ai/api/v1
hermes config set auxiliary.vision.api_key <your-openrouter-key>
```

要求该 provider 支持 OpenAI 兼容的 `chat.completions.create` 接口且支持 `image_url` 格式的 content 输入。

## 选项三：其他 OpenAI 兼容的视觉模型

任何支持 `image_url` 格式的 OpenAI 兼容 API 均可。格式示例：

```json
{
  "role": "user",
  "content": [
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
    {"type": "text", "text": "识别这张图的类型并提取内容..."}
  ]
}
```

配置方式同选项二。
