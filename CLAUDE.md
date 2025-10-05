# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个个人Python工具集合仓库,包含多个独立的实用工具脚本。这些工具主要用于媒体处理、文件转换和网络规则管理。

## 项目结构

### GUI应用程序 (`.pyw`文件)
- **mp4提取音频.pyw**: MP4到MP3音频提取器,使用Tkinter GUI和FFmpeg
- **转换mp4.pyw**: 通用视频格式转换器,支持多种视频格式到MP4转换
- **合并PDF.pyw**: 图片到PDF转换器,支持拖拽排序、图片预览
- **rules.pyw**: Clash和Surge网络规则文件格式转换器

### 命令行工具 (`.py`文件)
- **电影.py**: M3U8播放列表生成器,输出到`D:\movie`目录
- **FinalShell.py**: FinalShell激活码生成器(版本3.9.6前后)
- **逆向Mkey.py**: Mkey签名算法逆向工具

## 核心架构模式

### 1. GUI应用架构
所有`.pyw`文件遵循相似的Tkinter模式:
```python
# 标准结构:
# - 导入依赖(tkinter, threading, subprocess等)
# - 定义工具函数(文件操作、验证等)
# - 创建GUI类或函数
# - 使用threading处理长时间运行的操作(避免GUI冻结)
# - 进度条更新和状态反馈
# - 错误处理和用户提示
```

### 2. FFmpeg集成
视频/音频工具(`mp4提取音频.pyw`, `转换mp4.pyw`)使用FFmpeg:
- **检查可用性**: `shutil.which("ffmpeg")`或subprocess检测
- **获取视频信息**: 使用`ffprobe`提取时长、分辨率
- **进度监控**: 解析FFmpeg stderr输出中的`time=`字段
- **线程处理**: 使用`subprocess.Popen`异步执行,实时更新进度
- **Windows兼容**: 使用`creationflags=subprocess.CREATE_NO_WINDOW`隐藏控制台窗口

### 3. 文件处理模式
- **路径处理**: 统一使用`pathlib.Path`
- **编码处理**: UTF-8优先,GBK回退(`mp4提取音频.pyw`, `rules.pyw`)
- **输入验证**: 文件存在性、权限、完整性检查
- **默认目录**: `电影.py`默认输出到`D:\movie`, `rules.pyw`输出到`D:\Github\Surge\Rule`

## 常用开发模式

### 运行GUI应用
```bash
python <文件名>.pyw
# 或在Windows资源管理器中双击
```

### 运行命令行工具
```bash
python 电影.py
python FinalShell.py
python 逆向Mkey.py
```

## 关键技术要点

### GUI多线程模式
长时间操作必须在单独线程中执行:
```python
def start_conversion_thread(self):
    conversion_thread = threading.Thread(target=self.convert_to_mp3, daemon=True)
    conversion_thread.start()
```

### FFmpeg命令构建
```python
# 标准模式: 使用-y覆盖,-c:v编码器,-crf质量控制
command = f'ffmpeg -y -i "{input_file}" -c:v libx264 -crf {crf} -preset {preset} "{output_file}"'
```

### 正则表达式验证
- URL验证: `电影.py:validate_url()`使用完整的URL正则模式
- 时间解析: FFmpeg输出解析使用`re.search()`提取时间戳

### PDF生成 (合并PDF.pyw)
使用reportlab库,关键点:
- 使用`with`语句管理图片内存
- DPI转换: `pdf_w = width * 72.0 / dpi`
- 支持RGBA/WebP格式自动转RGB
- 最大尺寸限制4000像素避免内存溢出

### 规则文件处理 (rules.pyw)
- 分离文件头部注释和规则内容
- 自动更新元数据(时间戳、规则数量)
- 双格式输出: Clash YAML (`payload:`)和Surge LIST

## 依赖要求

### Python包
- tkinter (内置)
- PIL/Pillow (图片处理)
- reportlab (PDF生成)
- pycryptodome (加密哈希)

### 外部工具
- FFmpeg: 必须在PATH中,用于视频/音频处理

## 注意事项

- **Windows平台**: 代码针对Windows优化(路径、subprocess flags)
- **编码处理**: 文件操作优先UTF-8,视频输出需处理GBK
- **错误日志**: `转换mp4.pyw`会生成`ffmpeg_error.log`用于诊断
- **GUI响应性**: 所有耗时操作必须使用线程+`root.update_idletasks()`
