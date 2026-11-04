# /home/claude/tools/to_docs_md.py
# 📝 Экспорт макета (document.xml) в markdown по секциям для Claude Docs: s0 … s6.
# Правила: сквозная нумерация пунктов (numId=4) пишется явными числами; подпункты без номеров — вложенные «-»;
# таблицы 1×2 и СИЗ — pipe-таблицы; врезки-справки (таблицы 1×1) — цитаты; «Глава N⏎НАЗВАНИЕ» — заголовок + жирная строка.
import sys, re, os
from lxml import etree
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
src, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
body = etree.parse(src).getroot().find(W+'body')
els = list(body)

def esc(t):
    # ⚠️ экранируем символы, которые markdown воспримет как разметку
    return t.replace('\\','\\\\').replace('_','\\_').replace('*','\\*').replace('<','\\<').replace('`','\\`')

def runs_md(p):
    """Текст абзаца с жирным/курсивом на уровне runs."""
    parts=[]  # (text,bold,italic)
    for r in p.iter(W+'r'):
        rp=r.find(W+'rPr'); b=rp is not None and rp.find(W+'b') is not None and rp.find(W+'b').get(W+'val') not in ('0','false')
        i=rp is not None and rp.find(W+'i') is not None and rp.find(W+'i').get(W+'val') not in ('0','false')
        s=''
        for c in r:
            if c.tag==W+'t': s+=c.text or ''
            elif c.tag in (W+'tab',W+'br'): s+=' '
        if s: parts.append([s,b,i])
    # склейка соседних runs с одинаковым форматом
    m=[]
    for s,b,i in parts:
        if m and m[-1][1]==b and m[-1][2]==i: m[-1][0]+=s
        else: m.append([s,b,i])
    out=''
    for s,b,i in m:
        e=esc(s)
        if e.strip()=='' : out+=e; continue
        lead=e[:len(e)-len(e.lstrip())]; trail=e[len(e.rstrip()):]; core=e.strip()
        if b: core='**'+core+'**'
        if i: core='*'+core+'*'
        out+=lead+core+trail
    return out

def plain(p):
    return ''.join((c.text or '') if c.tag==W+'t' else (' ' if c.tag in (W+'tab',W+'br') else '')
                   for r in p.iter(W+'r') for c in r)

def numinfo(p):
    pp=p.find(W+'pPr')
    if pp is None or pp.find(W+'numPr') is None: return None
    return pp.find(W+'numPr').find(W+'numId').get(W+'val')
def style(p):
    pp=p.find(W+'pPr'); e=pp.find(W+'pStyle') if pp is not None else None
    return e.get(W+'val') if e is not None else ''

NOT_SUB=('[[ПОЛЕ: дополнительные','[[ПОЛЕ: исходные','[[ПОЛЕ: транспорт','[[ПОЛЕ: отклонения','[[ПОЛЕ: взрывы',
         '[[ПОЯСНЕНИЕ','[[СПРАВКА','[[ПОЛЕ: требования при','[[ПОЛЕ: СИЗ по типовым',
         # 🔧 ИЗМЕНЕНО: обычные абзацы-«вводки» блока СИЗ, а не подпункты
         'При необходимости работающему','[[ЕСЛИ: инструкция по виду работ]] При выполнении','[[ПОЛЕ: СИЗ для защиты')
def cell_text(tc):
    return ' '.join(x for x in (esc(plain(p)).strip() for p in tc.findall(W+'p')) if x).replace('|','\\|')

def render(idxs):
    out=[]; counter=getattr(render,'counter',0); prev=None  # prev: 'num' | 'sub' | 'plain:colon' | None
    for i in idxs:
        el=els[i]
        if el.tag==W+'p':
            t=plain(el).strip()
            if not t: prev=None; continue
            if numinfo(el)=='4':
                counter+=1; out.append(f'{counter}. {runs_md(el).strip()}'); prev='num'; continue
            st=style(el)
            is_head=bool(re.match(r'^Глава \d',t)) and el.find('.//'+W+'br') is not None
            if is_head:
                a,b=[x.strip() for x in re.split(r'⏎',''.join(('⏎' if c.tag==W+'br' else (c.text or '')) for r in el.iter(W+'r') for c in r if c.tag in (W+'t',W+'br')),1)]
                out.append(f'## {a}'); out.append('**'+esc(b)+'**'); prev=None; continue
            sub = (st in ('ConsNormal','ae') or prev in ('num','sub','bul','plain:colon') ) and not t.startswith(NOT_SUB)
            # 🔧 ИЗМЕНЕНО: различаем вложенные (под нумерованным пунктом) и обычные маркированные подпункты (под абзацем)
            if sub and prev in ('num','sub'):
                out.append('    - '+runs_md(el).strip()); prev='sub'
            elif sub:
                out.append('- '+runs_md(el).strip()); prev='bul'
            else:
                out.append(runs_md(el).strip()); prev='plain:colon' if t.endswith(':') else None
        elif el.tag==W+'tbl':
            prev=None
            rows=el.findall(W+'tr'); ncols=len(rows[0].findall(W+'tc'))
            if ncols==1:   # врезка-справка → цитата
                lines=[]
                for p in rows[0].find(W+'tc').findall(W+'p'):
                    t=runs_md(p).strip()
                    if t: lines.append('> '+t)
                out.append('\n>\n'.join(lines))
            else:
                tab=[[tc for tc in tr.findall(W+'tc')] for tr in rows]
                if len(tab)==1:   # одна строка из двух ячеек: первая строка текста ячейки — заголовок, остальное — тело
                    hdr=[];bod=[]
                    for tc in tab[0]:
                        ps=[esc(plain(p)).strip() for p in tc.findall(W+'p')]; ps=[x.replace('|','\\|') for x in ps]
                        nz=[x for x in ps if x]; hdr.append(nz[0] if nz else ' '); bod.append(' '.join(nz[1:]) if len(nz)>1 else ' ')
                    out.append('| '+' | '.join(hdr)+' |\n| '+' | '.join('---' for _ in hdr)+' |\n| '+' | '.join(bod)+' |')
                else:
                    L=[]
                    for ri,r in enumerate(tab):
                        L.append('| '+' | '.join((cell_text(tc) or ' ') for tc in r)+' |')
                        if ri==0: L.append('| '+' | '.join('---' for _ in r)+' |')
                    out.append('\n'.join(L))
    render.counter=counter
    return '\n\n'.join(out)+'\n'

# границы секций по индексам элементов тела
ranges={'s0':range(0,20),'s1':range(20,100),'s2':range(100,119),'s3':range(119,137),'s4':range(137,147),'s5':range(147,206),'s6':range(206,len(els))}
for k in ['s0','s1','s2','s3','s4','s5','s6']:
    md=render(ranges[k]); open(os.path.join(outdir,k+'.md'),'w',encoding='utf-8').write(md); print(k,len(md),'зн.')
print('последний номер пункта:',render.counter)
