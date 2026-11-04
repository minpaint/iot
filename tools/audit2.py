# /home/claude/tools/audit2.py
# 🔍 Сверка v3 (поля MACROBUTTON) → v4 (маркеры [[…]]): каждая фраза v3 ищется в v4,
# для ненайденных — ближайшая фраза v4 и коэффициент похожести.
import sys, re, difflib
sys.path.insert(0,'/home/claude/tools')
from audit import doc_text
def norm(s):
    s=s.replace(' ',' ').replace('–','—').replace('ё','е').replace('\u000b',' ')
    s=re.sub(r'\[\[(ЕСЛИ:[^\]]*|КОНЕЦ)\]\]','',s)
    s=re.sub(r'\[\[ПОЯСНЕНИЕ:\s*','',s); s=s.replace(']]',' @ ').replace('[[',' @ ')
    s=re.sub(r'\b[Рр]аботающ\w*','@',s)
    s=re.sub(r'(\s*@\s*)+',' @ ',s)
    return re.sub(r'\s+',' ',s).strip().lower()
def clauses(paras):
    out=[]
    for p in paras:
        for c in re.split(r'(?<=[;:])\s|(?<=\.)\s(?=[а-яa-z(«@])',norm(p)):
            c=c.strip(' ;:.,')
            if len(c)>=12: out.append(c)
    return out
v3=clauses(doc_text(sys.argv[1])); v4p=doc_text(sys.argv[2]); v4=' '.join(norm(p) for p in v4p); v4c=clauses(v4p)
seen=set(); miss=[]
for c in v3:
    if c in seen: continue
    seen.add(c)
    if c not in v4: miss.append(c)
print(f'v3 фраз {len(seen)}, нет дословно в v4: {len(miss)}\n')
for m in miss:
    best=max(v4c,key=lambda x: difflib.SequenceMatcher(None,m,x).ratio())
    r=difflib.SequenceMatcher(None,m,best).ratio()
    print(f'[{r:.2f}] v3: {m[:300]}\n       v4: {best[:300]}\n')
