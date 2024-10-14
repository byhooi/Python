import hashlib

def generate_mkey_sha1(data):
    return hashlib.sha1(data.encode()).hexdigest()

def generate_mkey_md5(data):
    return hashlib.md5(data.encode()).hexdigest()

token = 'WeixinMiniToken:719:31d6349f167d348af24758ea91c15dda10bb9e31'
url = '/clientApi/signInRecordAdd'
timestamp = '1724124247'
openid = 'ol4uQ5A8FEN8DFT3augaZ74KydhM'
version = '4.11.23'

# 尝试不同的数据组合
combinations = [
    f"{timestamp}.{token}.{openid}",    
    f"{token}{openid}{timestamp}",
    f"{token}{timestamp}{openid}",
    f"{url}{token}{timestamp}",
    f"{openid}{token}{timestamp}{version}",
    f"{token}{url}{openid}{timestamp}{version}"
    f"{token}{timestamp}"
    f"{timestamp}{token}"
]

target_mkey = '18ab155377daad3869d42b6ed4837837'

print("使用 SHA-1:")
for i, data in enumerate(combinations, 1):
    mkey = generate_mkey_sha1(data)
    print(f"组合 {i}: {mkey[:32]}... 匹配: {mkey[:32] == target_mkey}")

print("\n使用 MD5:")
for i, data in enumerate(combinations, 1):
    mkey = generate_mkey_md5(data)
    print(f"组合 {i}: {mkey} 匹配: {mkey == target_mkey}")