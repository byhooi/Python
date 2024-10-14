import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import urljoin

def get_page_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    return response.text

def extract_audio_links(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    audio_tags = soup.find_all('mpvoice')
    audio_links = []
    for tag in audio_tags:
        audio_url = tag.get('voice_encode_fileid')
        if audio_url:
            audio_links.append(audio_url)
    return audio_links

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def download_audio(audio_url, output_dir, index):
    try:
        response = requests.get(audio_url)
        response.raise_for_status()
        
        content_disposition = response.headers.get('content-disposition')
        if content_disposition:
            filename = re.findall("filename=(.+)", content_disposition)[0].strip('"')
        else:
            filename = f"audio_{index}.mp3"
        
        filename = sanitize_filename(filename)
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {filename}")
    except Exception as e:
        print(f"Error downloading audio {index}: {str(e)}")

def main():
    url = input("请输入微信公众号文章的URL: ")
    output_dir = input("请输入保存音频文件的目录路径: ")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    html_content = get_page_content(url)
    audio_links = extract_audio_links(html_content)
    
    for index, audio_link in enumerate(audio_links, start=1):
        full_audio_url = urljoin(url, audio_link)
        download_audio(full_audio_url, output_dir, index)
    
    print("下载完成!")

if __name__ == "__main__":
    main()