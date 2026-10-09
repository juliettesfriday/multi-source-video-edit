# 无私人素材的示例

这里的文案是示例，不来自真实视频。视频和字体需自行提供。

1. 把两段视频放入 clips/a.mp4 与 clips/b.mp4，并按它们的实际内容修改 edit.json。
2. `python3 ../scripts/assemble.py edit.json clean.mp4` 执行已经确认的片段表。
3. 提供与 clean.mp4 对齐的 captions.srt；把有权使用的字体放到 fonts/subtitle.ttf。
4. 修改 style.json 的章节时间；`python3 ../scripts/render_footer.py --config style.json --preview-at 1 --output preview.png` 先看截图。
5. 确认后 `python3 ../scripts/render_footer.py --config style.json --output final.mp4 --verify-decode`。
6. `python3 ../scripts/build_editor.py --srt captions.srt --video clean.mp4 --output editor.html` 创建校对页。导出修改后的 SRT，替换项目字幕或改配置指向它，再合成一个新文件。

脚本拒绝覆盖输出，再次运行请使用新的输出文件名。底栏脚本不代替逐句听音核对。
