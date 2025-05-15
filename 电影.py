def main():
    # 设置默认保存目录
    default_save_dir = r"D:\Downloads\Playlists"
    
    # 确保目录存在
    import os
    os.makedirs(default_save_dir, exist_ok=True)
    
    while True:  # 外层循环
        # 获取播放列表名称
        playlist_name = input("请输入播放列表的名称（不需要扩展名），输入 'q' 退出程序: ").strip()
        if playlist_name.lower() == 'q':  # 检查是否要退出程序
            break
        if not playlist_name:
            playlist_name = "playlist"
        playlist_name += ".m3u8"
        
        print("请输入视频链接，格式为 '标题 https://链接' 或 '标题$https://链接'，直接回车结束。")
        videos = []
        while True:
            input_str = input()
            if input_str == '':
                break
            videos.append(input_str)
        
        if not videos:  # 如果没有输入视频链接，继续下一轮
            print("未输入任何视频链接！")
            continue
            
        # 构建完整的文件路径
        full_path = os.path.join(default_save_dir, playlist_name)

        # 创建m3u8文件
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n\n')
            for video in videos:
                try:
                    if ' ' in video:
                        title, link = video.rsplit(' ', 1)
                    elif '$' in video:
                        title, link = video.rsplit('$', 1)
                    else:
                        raise ValueError("无法识别的分割符")
                    title = title.strip()
                    link = link.strip()
                    f.write(f'#EXTINF:-1,{title}\n{link}\n\n')
                except ValueError as e:
                    print(f"输入格式错误，跳过此项：{video}，错误信息：{e}")

        print(f"播放列表已创建为 '{full_path}'")
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()
