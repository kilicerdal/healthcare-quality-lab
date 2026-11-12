"""Render the project report's small, explicit Markdown subset to printable HTML."""
import html
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def inline(text):
    text=html.escape(text)
    text=re.sub(r"`([^`]+)`",r"<code>\1</code>",text)
    text=re.sub(r"\*\*([^*]+)\*\*",r"<strong>\1</strong>",text)
    text=re.sub(r"\[([^]]+)\]\((https?://[^)]+)\)",r'<a href="\2">\1</a>',text)
    return text


def render(source, version="v3"):
    lines=source.splitlines()
    result=[];toc=[];index=0
    while index<len(lines):
        line=lines[index]
        if not line.strip():
            index+=1;continue
        if line.startswith("```"):
            code=[];index+=1
            while index<len(lines) and not lines[index].startswith("```"):
                code.append(lines[index]);index+=1
            result.append("<pre><code>"+html.escape("\n".join(code))+"</code></pre>")
            index+=1;continue
        if line.startswith("#"):
            level=len(line)-len(line.lstrip("#"));title=line[level:].strip();anchor=re.sub(r"[^a-z0-9]+","-",title.lower()).strip("-")
            if level==2:toc.append((anchor,title))
            result.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>')
            index+=1;continue
        if line.startswith("| "):
            rows=[]
            while index<len(lines) and lines[index].startswith("|"):
                cells=[c.strip() for c in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+",c) for c in cells):rows.append(cells)
                index+=1
            if rows:
                head="".join("<th>"+inline(c)+"</th>" for c in rows[0])
                body="".join("<tr>"+"".join("<td>"+inline(c)+"</td>" for c in row)+"</tr>" for row in rows[1:])
                result.append('<div class="table-wrap"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>')
            continue
        if line.startswith("- "):
            items=[]
            while index<len(lines) and lines[index].startswith("- "):
                items.append("<li>"+inline(lines[index][2:])+"</li>");index+=1
            result.append("<ul>"+"".join(items)+"</ul>");continue
        paragraph=[]
        while index<len(lines) and lines[index].strip() and not lines[index].startswith(("#","```","- ","| ")):
            paragraph.append(lines[index]);index+=1
        result.append("<p>"+inline(" ".join(paragraph))+"</p>")
    nav="".join(f'<a href="#{anchor}">{html.escape(title)}</a>' for anchor,title in toc)
    css="""*{box-sizing:border-box}body{margin:0;background:#f4f6ef;color:#243a30;font-family:system-ui,sans-serif}header{padding:32px max(25px,calc((100vw - 1100px)/2));background:#193f2c;color:#edf4e4;display:flex;justify-content:space-between;align-items:center;gap:20px}header span{font-size:11px;letter-spacing:2px}button{padding:10px 15px;border:1px solid #8ea66e;background:transparent;color:#e1edce;border-radius:5px;cursor:pointer}main{max-width:1100px;margin:35px auto;display:grid;grid-template-columns:215px 1fr;gap:35px;padding:0 25px}nav{position:sticky;top:25px;align-self:start;max-height:90vh;overflow:auto;font-size:10px;line-height:1.7}nav strong{display:block;margin:8px 0 18px;color:#698158;font-size:10px;letter-spacing:1.5px}nav a{display:block;color:#7e8e70;text-decoration:none;padding:7px 0}article{background:#fff;border:1px solid #dce4d4;border-radius:10px;padding:38px;min-width:0}h1{font-family:Georgia,serif;font-size:34px;line-height:1.2;font-weight:400;color:#264d32;margin:0 0 25px}h2{font-size:20px;line-height:1.4;margin-top:38px;padding-top:18px;border-top:1px solid #e4eadc;scroll-margin-top:25px}h3{font-size:15px;margin-top:25px}p,li{font-size:12px;line-height:1.95;color:#68795f}li{margin:8px 0}strong{color:#405d34}a{color:#397042}code{font:10px/1.8 ui-monospace,monospace;background:#f2f5ea;border-radius:3px;padding:2px 4px;overflow-wrap:anywhere}pre{background:#f2f5ea;padding:18px;border-radius:6px;overflow:auto;white-space:pre-wrap}pre code{padding:0}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:10px;line-height:1.8;margin:20px 0}th,td{text-align:left;padding:12px;border:1px solid #dfe7d5;vertical-align:top}th{background:#edf3e3;color:#527340}td{color:#718263}.architecture{margin:28px 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:10px;color:#728464}.architecture span{background:#edf4e3;border:1px solid #dce8c9;padding:12px;border-radius:5px}footer{text-align:center;font-size:10px;color:#98a78a;padding:25px 20px 45px}@media(max-width:800px){main{display:block;padding:0 16px}nav{position:static;margin-bottom:25px;columns:2}article{padding:25px}h1{font-size:29px}header{padding:22px}nav a{font-size:9px}}@media print{body{background:white}header,nav,button,footer{display:none}main{display:block;max-width:none;margin:0;padding:0}article{border:0;padding:0}p,li{font-size:10pt;line-height:1.6;color:#222}h1{font-size:25pt}h2{break-after:avoid}table,pre,.architecture{break-inside:avoid}a{color:#222}code{font-size:9pt}th,td{font-size:8pt}}"""
    diagram='<div class="architecture"><span>Written contracts</span>→<span>Python evaluator</span>→<span>Flask API</span>→<span>Browser workflow</span>→<span>Recorded evidence</span></div>'
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Healthcare Quality Lab '+version.upper()+' Engineering Report</title><style>'+css+'</style></head><body><header><span>HEALTHCARE QUALITY LAB / '+version.upper()+' ENGINEERING REPORT</span><button onclick="window.print()">Print / Save PDF</button></header><main><nav><strong>IN THIS REPORT</strong>'+nav+'</nav><article>'+diagram+"".join(result)+'</article></main><footer>'+version.upper()+' · Synthetic contracts · Evidence and limitations recorded together</footer></body></html>')


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--version",choices=("v1","v2","v3","v4","v5","v5.1"),default="v5.1")
    args=parser.parse_args()
    name=args.version.upper()+"_REPORT"
    source=(ROOT/f"docs/{name}.md").read_text()
    (ROOT/f"docs/{name}.html").write_text(render(source,args.version))
    print(f"Rendered docs/{name}.html")

if __name__=="__main__":
    main()
