# 多素材剪辑（含字幕进度条）

一个面向 AI 编程助手的口播 / PPT 视频剪辑 skill。支持从多个素材整理成片，也支持只改一个现有视频。保守剪辑、可编辑字幕、章节进度条、高清导出，以及“只改这一次要求的部分”。

**不是一键自动剪辑软件**：skill 指导助手理解口播和作出剪辑判断，脚本执行已经确定的时间轴。不内置语音识别模型，不会自动决定删哪句话。

内部标识：`multi-source-video-edit`；界面显示：**多素材剪辑（含字幕进度条）**。

## See the skill in action / 效果宣传片

https://github.com/user-attachments/assets/1bc462da-41e7-4d62-bb03-79458c12af22

**English narration · English-first headlines · 中文小注释与双语字幕 · 60 seconds · 1080p**

Multiple clips. One first cut. See how the skill helps an AI assistant assemble clips, remove silent gaps and adjacent repeats, and add editable subtitles and chapter progress.

用美妆数字人示例展示多段合一、去空白与相邻重复、字幕与章节进度条，以及后续字幕修改。

The before/after footage is a constructed demo with deliberately added pauses and a repeated take. 14.7 s → 4.9 s describes this demo’s content duration, not processing speed. The original avatar provider watermark is retained.

演示素材刻意加入停顿和重复；时长对比指素材内容长度，不代表实际处理耗时。保留数字人来源水印。

## Video walkthrough / 使用示范

https://github.com/user-attachments/assets/7bffbe0c-5818-48b1-bccd-1eae3882d2b6

**English narration · 中英文双语字幕 · 90 seconds · 1080p**

[Watch / download the video](https://github.com/juliettesfriday/multi-source-video-edit/raw/refs/heads/main/docs/skill-demo-en-zh.mp4) · [Download bilingual subtitles](docs/skill-demo-en-zh.srt)

A short walkthrough of installation, prompting, conservative cuts, caption styling, chapter progress, and subtitle corrections. The interface and timeline are illustrative workflow graphics, not a recording of an automatic editing app. No private footage is included.

演示安装、下指令、保守剪辑、字幕与章节进度条，以及后续改字。画面使用流程示意，不是一键自动剪辑软件的实录；不包含私人视频素材。

## 安装与使用

把本仓库目录命名为 `multi-source-video-edit`，放进 Codex 的 skills 目录：默认 `~/.codex/skills/`，自定义环境则使用 `$CODEX_HOME/skills/`。已存在同名目录时先备份，不直接覆盖。重新打开任务以载入技能。

可直接说：

- “用多素材剪辑（含字幕进度条），把这几个口播视频剪顺；保留有效内容。”
- “使用 $multi-source-video-edit，给这个视频加大字幕和章节进度条，先给截图。”
- “从这句话开始裁切当前成片，其他都不变，尽可能保持清晰度。”

口播稿、多段素材都**不是必填项**。已有项目沿用现有资料，只补充真正缺少的信息。新要求覆盖历史预设；不把任何示例切点或章节当作固定要求。

## 能力范围

| 内容 | 提供方式 |
| --- | --- |
| 保守删停顿、卡壳、相邻重复 | skill 判断流程、删除清单与可恢复 EDL |
| 素材检查、已有成片精准裁切、EDL拼接 | 可运行 Python / FFmpeg 脚本 |
| SRT 校对、裁切平移、多段映射 | 可运行脚本，切口字幕会输出复核报告 |
| A100字幕、C章节进度条 | 可配置预设、截图预览和完整合成脚本 |
| 后续改字幕 | 离线校对页面：搜索、试听、改字、时间、导入导出 |
| 磨皮、PPT翻书、图文、封面 | 按需工作流指导；需要助手使用合适的图像/视频工具，不包含自动实现这些效果的脚本 |

A100 是参考宽度3240时的100像素字幕、420像素底栏，默认白字无描边；其他尺寸按比例适配。C为蓝紫章节进度条。它们是可选预设，不强制套用。画面内进度条不可点击，拖动由播放器完成。

## 本地运行依赖

Python **3.11+**、FFmpeg 和 ffprobe。底栏渲染/截图需要 Pillow：

```sh
python3 -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell 使用 .venv\Scripts\Activate.ps1
python3 -m pip install -r requirements.txt
```

核心脚本无需账号或网络服务。中文字体请自行提供有权使用的 TTF/OTF，仓库不捆绑字体。默认建议小赖风格，也可换成喜欢的字体。

## 示例

从某个完整句首裁切，输出另存，原文件不变：

```sh
python3 scripts/trim.py input.mp4 output.mp4 --start 51.567 --verify-decode
```

秒数只是用法示例，实际切点先听看确认。MP4裁切使用 edit list，不重编码；文件内可保留不可见解码参考帧，不适用于物理擦除敏感片段。需在目标播放器或发布平台验证。

完整合成示例见 [examples/](examples/)。所有路径为示例，不含私人素材。

- [主技能](SKILL.md)：助手的决策规则
- [精剪流程](references/editing.md)：删除清单、时间轴、句首裁切
- [字幕与进度条](references/captions-progress.md)：配置和可编辑字幕
- [工具与质量](references/quality-tools.md)：完整命令和验证原则

## 测试与限制

```sh
python3 -m unittest discover -s tests -v
```

测试只生成几秒的色块/测试画面与正弦音，不使用真人、语音或私人文件。媒体测试需本机 FFmpeg，渲染测试需 Pillow 与测试字体；不可用时会明确跳过，不能将跳过视为验证完成。可通过 `TEST_FONT` 提供字体。

当前底栏和拼接辅助脚本支持方向标准化、8位SDR、固定帧率素材。HDR、旋转、VFR等输入需要专门处理，脚本会阻止静默降级。无损裁切脚本用于MP4可容纳的编码。烧录字幕、拼接、改画面通常需要重编码，不承诺数学无损。不自动清除噪音、调整响度或添加音乐。

## 开源与发布

MIT许可覆盖本仓库自有代码、文档和模板；FFmpeg、Pillow、外部字体及用户素材分别遵循各自许可，不能因本仓库为MIT而视为可自由再分发。

发布仅推送这个独立目录，不能推送视频项目的父目录。不要提交源视频、人像、字幕全文、账户信息、私有路径、字体文件或模型权重。`.gitignore` 是辅助，不代替检查实际待提交文件。

可在GitHub创建空仓库，再在本目录初始化Git、提交并连接该仓库推送。创建公开仓库/上传属于对外发布，应核对账户和目标仓库后执行。

拼接/底栏辅助脚本要求单画轨、最多单音轨，额外音轨或内嵌字幕须先明确处理，不能静默丢失。不同色彩元数据的素材需先明确统一方式。无损裁切脚本会保留所有支持的画轨、音轨和字幕轨。
