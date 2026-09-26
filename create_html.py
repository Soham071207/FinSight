import json

with open('FinSight_IEEE_Paper_FINAL.txt', 'r', encoding='utf-8') as f:
    md_text = f.read()

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>FinSight IEEE Paper</title>
    <style>
        body {{ 
            font-family: 'Times New Roman', Times, serif; 
            line-height: 1.6; 
            margin: 40px auto; 
            max-width: 900px; 
            padding: 0 40px; 
            color: #222; 
            background-color: #fdfdfd;
            text-align: justify;
        }}
        h1, h2, h3, h4 {{ 
            font-family: 'Georgia', serif; 
            color: #111; 
            margin-top: 30px; 
        }}
        h1 {{ text-align: center; font-size: 2.2em; margin-bottom: 10px; }}
        h2 {{ border-bottom: 1px solid #aaa; padding-bottom: 5px; margin-top: 40px; font-variant: small-caps;}}
        h3 {{ font-style: italic; }}
        table {{ 
            border-collapse: collapse; 
            width: 100%; 
            margin: 25px 0; 
            font-size: 0.95em; 
            box-shadow: 0 0 10px rgba(0,0,0,0.05);
            background-color: #fff;
        }}
        th, td {{ 
            border: 1px solid #ddd; 
            padding: 12px 15px; 
            text-align: left; 
        }}
        th {{ 
            background-color: #f8f9fa; 
            font-weight: bold; 
            border-bottom: 2px solid #555;
            text-transform: uppercase;
            font-size: 0.9em;
            letter-spacing: 0.5px;
        }}
        tr:nth-child(even) {{ background-color: #fafafa; }}
        pre {{ 
            background-color: #f5f5f5; 
            padding: 15px; 
            overflow-x: auto; 
            border-left: 4px solid #777; 
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.9em;
        }}
        code {{ 
            font-family: 'Courier New', Courier, monospace; 
            background-color: #f5f5f5; 
            padding: 2px 4px; 
            font-size: 0.95em;
        }}
        hr {{ 
            border: 0; 
            height: 1px; 
            background-image: linear-gradient(to right, rgba(0, 0, 0, 0), rgba(0, 0, 0, 0.75), rgba(0, 0, 0, 0)); 
            margin: 40px 0; 
        }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        blockquote {{
            border-left: 3px solid #ccc;
            margin: 20px 0;
            padding-left: 20px;
            font-style: italic;
            color: #555;
        }}
    </style>
    <!-- Load marked.js to render Markdown in the browser -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>
      // Support LaTeX math blocks by protecting them from Marked.js
      window.MathJax = {{
        tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']], displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']] }},
        svg: {{ fontCache: 'global' }}
      }};
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body>
    <div id="content"></div>
    <script>
        // The raw markdown is injected here safely as a JSON string
        const mdText = {json.dumps(md_text)};
        document.getElementById('content').innerHTML = marked.parse(mdText);
    </script>
</body>
</html>
"""

with open('FinSight_IEEE_Paper_Formatted.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Created FinSight_IEEE_Paper_Formatted.html")
