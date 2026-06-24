#!/usr/bin/env python3
"""render_graph.py — turn graph.json into a standalone offline graph.html.

Zero dependencies. Reads graph.json beside this script and writes graph.html
with a small force-directed view (inline vanilla JS canvas — no CDN, works
offline). Regenerate after structural code changes:

    python .agents/graph/render_graph.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "graph.json"), "r", encoding="utf-8") as f:
        g = json.load(f)
    data = json.dumps({"nodes": g.get("nodes", []), "edges": g.get("edges", [])})
    title = g.get("project", "Repo") + " — knowledge graph"
    html = _TEMPLATE.replace("__TITLE__", title).replace("__DATA__", data)
    out = os.path.join(HERE, "graph.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote %s (%d nodes, %d edges)"
          % (out, len(g.get("nodes", [])), len(g.get("edges", []))))


_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
  html,body{margin:0;background:#0A0A14;color:#e6e6f0;font:14px/1.4 system-ui,sans-serif}
  header{padding:12px 16px;border-bottom:1px solid #1e1e30}
  h1{font-size:15px;margin:0;color:#06B6D4}
  #wrap{display:flex;height:calc(100vh - 50px)}
  canvas{flex:1;display:block}
  aside{width:320px;overflow:auto;border-left:1px solid #1e1e30;padding:12px;font-size:12px}
  .n{padding:6px 8px;border-radius:6px;margin-bottom:4px;background:#12121f}
  .n b{color:#8B5CF6}
  code{color:#22C55E}
</style></head><body>
<header><h1>__TITLE__</h1></header>
<div id="wrap"><canvas id="c"></canvas>
<aside id="list"></aside></div>
<script>
const G = __DATA__;
const cv = document.getElementById('c'), cx = cv.getContext('2d');
function size(){cv.width=cv.clientWidth;cv.height=cv.clientHeight;}
window.addEventListener('resize',size);size();
const N=G.nodes, E=G.edges, idx={};
N.forEach((n,i)=>{idx[n.id]=i;n.x=cv.width/2+Math.cos(i)*200*Math.random();n.y=cv.height/2+Math.sin(i)*200*Math.random();n.vx=0;n.vy=0;});
function step(){
  for(let i=0;i<N.length;i++)for(let j=i+1;j<N.length;j++){
    let a=N[i],b=N[j],dx=a.x-b.x,dy=a.y-b.y,d=Math.hypot(dx,dy)||1,f=2200/(d*d);
    a.vx+=dx/d*f;a.vy+=dy/d*f;b.vx-=dx/d*f;b.vy-=dy/d*f;}
  E.forEach(e=>{let a=N[idx[e.from]],b=N[idx[e.to]];if(!a||!b)return;
    let dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy)||1,f=(d-120)*0.01;
    a.vx+=dx/d*f;a.vy+=dy/d*f;b.vx-=dx/d*f;b.vy-=dy/d*f;});
  N.forEach(n=>{n.vx*=0.85;n.vy*=0.85;n.x+=n.vx;n.y+=n.vy;
    n.x=Math.max(40,Math.min(cv.width-40,n.x));n.y=Math.max(40,Math.min(cv.height-40,n.y));});
}
const COL={entry:'#22C55E',module:'#06B6D4',new:'#8B5CF6',doc:'#888',default:'#06B6D4'};
function draw(){
  cx.clearRect(0,0,cv.width,cv.height);
  cx.strokeStyle='#2a2a40';cx.lineWidth=1;
  E.forEach(e=>{let a=N[idx[e.from]],b=N[idx[e.to]];if(!a||!b)return;
    cx.beginPath();cx.moveTo(a.x,a.y);cx.lineTo(b.x,b.y);cx.stroke();});
  N.forEach(n=>{cx.fillStyle=COL[n.type]||COL.default;
    cx.beginPath();cx.arc(n.x,n.y,7,0,7);cx.fill();
    cx.fillStyle='#cfcfe0';cx.font='11px system-ui';cx.fillText(n.id,n.x+10,n.y+4);});
}
function loop(){for(let k=0;k<3;k++)step();draw();requestAnimationFrame(loop);}
loop();
document.getElementById('list').innerHTML=N.map(n=>
  '<div class="n"><b>'+n.id+'</b> <code>'+(n.path||'')+'</code><br>'+(n.desc||'')+'</div>').join('');
</script></body></html>
"""


if __name__ == "__main__":
    main()
