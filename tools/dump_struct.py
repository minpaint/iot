# /home/claude/tools/dump_struct.py
# 🔍 Дамп структуры document.xml: тип элемента, нумерация, отступ, выравнивание, жирность, текст (с w:br/w:tab).
import sys
from lxml import etree
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
def txt(p):
    o=[]
    for r in p.iter(W+'r'):
        for c in r:
            if c.tag==W+'t': o.append(c.text or '')
            elif c.tag==W+'tab': o.append('\t')
            elif c.tag==W+'br': o.append('⏎')
    return ''.join(o)
def info(p):
    pp=p.find(W+'pPr'); n=il=ind=jc=st=''
    if pp is not None:
        e=pp.find(W+'numPr')
        if e is not None:
            n=e.find(W+'numId').get(W+'val'); il=e.find(W+'ilvl').get(W+'val') if e.find(W+'ilvl') is not None else '0'
        e=pp.find(W+'ind'); ind=(e.get(W+'left') or e.get(W+'start') or '') if e is not None else ''
        e=pp.find(W+'jc'); jc=e.get(W+'val') if e is not None else ''
        e=pp.find(W+'pStyle'); st=e.get(W+'val') if e is not None else ''
    rs=[r for r in p.findall(W+'r') if r.find(W+'t') is not None]
    bold=bool(rs) and all(r.find(W+'rPr') is not None and r.find(W+'rPr').find(W+'b') is not None for r in rs)
    return n,il,ind,jc,st,bold
b=etree.parse(sys.argv[1]).getroot().find(W+'body')
for i,el in enumerate(b):
    if el.tag==W+'p':
        n,il,ind,jc,st,bd=info(el); t=txt(el)
        print(f'{i:3} P num={n}/{il} ind={ind} jc={jc} st={st} b={int(bd)} | {t[:95]}')
    elif el.tag==W+'tbl':
        rows=el.findall(W+'tr'); print(f'{i:3} TABLE rows={len(rows)} cols={len(rows[0].findall(W+"tc"))}')
