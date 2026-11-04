# /home/claude/tools/extract.py
# 📄 Извлечение текста из document.xml с маркерами: MACROBUTTON → ⟦...⟧, выделение цветом → {цвет:...}, курсив → _..._
import sys, re
from lxml import etree
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
def q(t): return W+t
doc=etree.parse(sys.argv[1])
body=doc.getroot().find(q('body'))
def para_text(p):
    out=[]; in_instr=False; instr=''; field_depth=0; show_result=True
    for r in p.iter(q('r')):
        fc=r.find(q('fldChar'))
        if fc is not None:
            t=fc.get(q('fldCharType'))
            if t=='begin': field_depth+=1; instr=''; in_instr=True
            elif t=='separate': in_instr=False
            elif t=='end':
                if in_instr and 'MACROBUTTON' in instr:
                    m=re.sub(r'\s*MACROBUTTON\s+\S+\s*','',instr,1)
                    out.append('⟦'+m.strip()+'⟧')
                in_instr=False; field_depth-=1
            continue
        it=r.find(q('instrText'))
        if it is not None: instr+=it.text or ''; continue
        if in_instr: continue
        rpr=r.find(q('rPr')); hl=None; ital=False; vanish=False
        if rpr is not None:
            h=rpr.find(q('highlight')); hl=h.get(q('val')) if h is not None else None
            ital=rpr.find(q('i')) is not None and rpr.find(q('i')).get(q('val')) not in ('0','false')
            vanish=rpr.find(q('vanish')) is not None
        txt=''.join((e.text or '') if e.tag==q('t') else ('\t' if e.tag==q('tab') else ('\n' if e.tag==q('br') else '')) for e in r)
        if not txt or vanish: continue
        if hl: txt='{'+hl[:2]+':'+txt+'}'
        if ital: txt='_'+txt+'_'
        out.append(txt)
    s=''.join(out)
    s=re.sub(r'\}\{(\w\w):','',s) if False else s
    return s
def walk(el,depth=0):
    for ch in el:
        if ch.tag==q('p'):
            ppr=ch.find(q('pPr')); num=''
            if ppr is not None and ppr.find(q('numPr')) is not None:
                np_=ppr.find(q('numPr')); il=np_.find(q('ilvl')); ni=np_.find(q('numId'))
                num=f"[num{ni.get(q('val')) if ni is not None else '?'}.L{il.get(q('val')) if il is not None else 0}] "
            st=ppr.find(q('pStyle')).get(q('val')) if ppr is not None and ppr.find(q('pStyle')) is not None else ''
            t=para_text(ch)
            if t.strip() or num: print('  '*depth+(f'<{st}> ' if st else '')+num+t)
        elif ch.tag==q('tbl'):
            print('  '*depth+'=== TABLE')
            for tr in ch.findall(q('tr')):
                for tc in tr.findall(q('tc')):
                    print('  '*depth+'| cell:'); walk(tc,depth+1)
            print('  '*depth+'=== /TABLE')
        elif ch.tag==q('sdt'):
            c=ch.find(q('sdtContent'))
            if c is not None: walk(c,depth)
walk(body)
