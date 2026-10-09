# 质量与工具

依赖 Python3、ffmpeg、ffprobe。底栏渲染需 Pillow（requirements.txt）。不含ASR模型，不需账号或外部服务；自动转写由代理按环境选工具。

以下从 skill 根目录运行，替换为本次实际文件：

```sh
python3 scripts/inspect_media.py clip-a.mp4 clip-b.mp4 --output inventory.json
python3 scripts/trim.py edited.mp4 trimmed.mp4 --start 51.567 --verify-decode
python3 scripts/assemble.py project/edit.json joined.mp4
python3 scripts/captions.py validate captions.srt
python3 scripts/captions.py trim captions.srt trimmed.srt --start 51.567
python3 scripts/captions.py map project/edit.json project/subtitles.json mapped.srt
python3 scripts/render_footer.py --config project/style.json --preview-at 12 --output preview.png
python3 scripts/render_footer.py --config project/style.json --output captioned.mp4
python3 scripts/build_editor.py --srt captions.srt --video clean.mp4 --output project/editor.html
```

subtitles.json 是源片到字幕的映射，例如 {"clips/a.mp4":"captions/a.srt"}，相对路径按该映射文件所在目录解析，与EDL解析后的实际路径匹配。

异尺寸/帧率拼接需明确 --width --height --fps。assemble.py 保持比例居中容纳，不裁切、不自动选1080p；统一格式方案由实际素材与用户目标决定。上采样不等于新增细节。工具不会自动降噪、变速、加音乐或改响度。

工具拒绝覆盖输入和已有输出，先写临时输出、成功后发布；素材与配置存项目目录，技能目录作为只读工具源。

## 质量策略

- 只裁切：优先 MP4 流复制+edit list，并验证实际起播。容器不支持源编码时选择合适容器或说明必要重编码，不能仅改扩展名。
- 拼接/烧录图形：尽量从原素材或干净底片一次合成。SDR H.264 CRF14可作高质量起点，按素材调整；不是无损保证。
- HDR、10位、旋转、VFR：先读元数据，采用对应处理；不能无声降成普通SDR。
- 音视频使用同一裁切位置；响度、音乐、降噪另按授权处理。

检查源身份、分辨率、帧率、方向、色彩、时长、字幕溢出、章节位置。无损裁切核验压缩包哈希与首帧，解码帧数排除不可见参考帧；必要时波形检查音频偏移。整片完整解码，重点看首句、切缝、最长字幕和片尾；通过且无新改动不反复测试。未实测某平台，不声称兼容它。

上传/发布是与本地导出不同的动作，剪辑授权不自动包含对外发布。

拼接/底栏辅助脚本要求单画轨、最多单音轨，额外音轨或内嵌字幕须先明确处理，不能静默丢失。不同色彩元数据的素材需先明确统一方式。无损裁切脚本会保留所有支持的画轨、音轨和字幕轨。
