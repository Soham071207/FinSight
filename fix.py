import base64
import os

html_path = 'FinSight_Aavishkar_Poster.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

images = [
    'STOCK/market_regime_plot.png',
    'STOCK/equity_curve.png'
]

for img in images:
    if os.path.exists(img):
        with open(img, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            b64_src = f'data:image/png;base64,{encoded_string}'
            content = content.replace(f'src="{img}"', f'src="{b64_src}"')
    else:
        print(f"Could not find {img}")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done injecting base64 images.')
