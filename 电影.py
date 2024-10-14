def main():
    # 获取播放列表名称
    playlist_name = input("请输入播放列表的名称（不需要扩展名）: ").strip()
    if not playlist_name:
        playlist_name = "playlist"  # 如果用户没有输入名称，则使用默认名称
    playlist_name += ".m3u8"  # 添加文件扩展名

    print("请输入视频链接，格式为 '标题 https://链接' 或 '标题$https://链接'，直接回车结束。")
    videos = []
    while True:
        # 获取用户输入
        input_str = input()
        if input_str == '':  # 检查输入是否为空字符串
            break
        videos.append(input_str)

    # 创建m3u8文件
    with open(playlist_name, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')
        for video in videos:
            try:
                # 检查输入格式，并据此分割字符串
                if ' ' in video:
                    title, link = video.rsplit(' ', 1)  # 使用空格分割字符串，最多分割一次
                elif '$' in video:
                    title, link = video.rsplit('$', 1)  # 使用$分割字符串，最多分割一次
                else:
                    raise ValueError("无法识别的分割符")
                title = title.strip()  # 移除标题两端的空白字符
                link = link.strip()  # 移除链接两端的空白字符
                f.write(f'#EXTINF:-1,{title}\n{link}\n\n')  # 写入文件
            except ValueError as e:
                print(f"输入格式错误，跳过此项：{video}，错误信息：{e}")

    print(f"播放列表已创建为 '{playlist_name}'")

if __name__ == "__main__":
    main()
