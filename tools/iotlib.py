# /home/claude/tools/iotlib.py
# 🧰 Библиотека сборки ИОТ по макету с маркерами [[…]] (работа с распакованным docx, lxml).
# Ключевая идея: весь текст абзацев документа склеивается в одну строку с разделителем «\n»,
# маркеры ищутся регулярками, а удаление диапазона переводится обратно в абзацы и runs.
import copy, re
from lxml import etree
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def q(t): return '{%s}%s'%(W,t)
XS='{http://www.w3.org/XML/1998/namespace}space'

class Doc:
    def __init__(self, path):
        self.path=path; self.tree=etree.parse(path); self.body=self.tree.getroot().find(q('body'))
        # 🔧 ИЗМЕНЕНО: убираем служебные отметки w:lastRenderedPageBreak (подсказки отрисовки Word, ни на что не влияют).
        # ⚠️ Без этого run с двумя w:t (текст до и после отметки) дублировал хвост при split_at.
        for el in list(self.tree.getroot().iter(q('lastRenderedPageBreak'))):
            el.getparent().remove(el)
        # 🔧 ИЗМЕНЕНО: run, где больше одного содержимого (несколько w:t, w:t + w:tab/w:br), разбиваем на отдельные run
        #    с копией w:rPr. Иначе split_at дублирует «хвост» run (баг: «отражаются:» в п.35).
        for r in list(self.tree.getroot().iter(q('r'))):
            kids=[c for c in r if c.tag!=q('rPr')]
            if len(kids)>1 and any(c.tag==q('t') for c in kids):
                rpr=r.find(q('rPr')); prev=r
                for c in kids[1:]:
                    nr=etree.SubElement(r.getparent(),q('r')); r.getparent().remove(nr)
                    if rpr is not None: nr.append(copy.deepcopy(rpr))
                    r.remove(c); nr.append(c); prev.addnext(nr); prev=nr
        self.touched=set()   # абзацы, которые мы меняли (пустые после правок — удаляются)
        self.ever=set()      # все когда-либо изменённые абзацы (для чистки пробелов)
    def save(self): self.tree.write(self.path, xml_declaration=True, encoding='UTF-8', standalone=True)
    # ---------- текст ----------
    def paras(self): return [p for p in self.body.iter(q('p'))]
    @staticmethod
    def truns(p): return [r for r in p.iter(q('r')) if r.find(q('t')) is not None]
    @staticmethod
    def ptext(p): return ''.join(t.text or '' for t in p.iter(q('t')))
    def text(self):
        ps=self.paras(); offs=[]; s=''; 
        for p in ps:
            offs.append(len(s)); s+=self.ptext(p)+'\n'
        return s, ps, offs
    def locate(self, pos, ps, offs):
        import bisect
        i=bisect.bisect_right(offs,pos)-1; return i, pos-offs[i]
    # ---------- операции внутри абзаца ----------
    def split_at(self, p, cut):
        pos=0
        for r in self.truns(p):
            t=r.find(q('t')); L=len(t.text or '')
            if pos<cut<pos+L:
                assert len(r.findall(q('t')))==1, 'split_at: в run несколько w:t'   # ⚠️ защита от дублирования текста
                right=copy.deepcopy(r); right.find(q('t')).text=t.text[cut-pos:]; right.find(q('t')).set(XS,'preserve')
                t.text=t.text[:cut-pos]; t.set(XS,'preserve'); r.addnext(right); return
            pos+=L
    def del_chars(self, p, a, b):
        if a>=b: return
        self.split_at(p,b); self.split_at(p,a); pos=0
        for r in self.truns(p):
            L=len(r.find(q('t')).text or '')
            if pos>=a and pos+L<=b and L: r.getparent().remove(r)
            pos+=L
        self.touched.add(p); self.ever.add(p)
    def replace_in(self, p, a, b, new):
        """Заменяет символы [a,b) абзаца на new, сохраняя оформление первого run диапазона."""
        self.split_at(p,b); self.split_at(p,a); pos=0; first=None
        for r in self.truns(p):
            L=len(r.find(q('t')).text or '')
            if pos>=a and pos+L<=b and L:
                if first is None: first=r
                else: r.getparent().remove(r)
            pos+=L
        if first is None:   # пустой диапазон — вставка
            for r in self.truns(p): pass
        t=first.find(q('t')); t.text=new; t.set(XS,'preserve'); self.touched.add(p); self.ever.add(p)
    # ---------- удаление глобального диапазона [A,B) ----------
    def top(self, el):
        """Ближайший предок, лежащий в том же контейнере, что и el (body или ячейка)."""
        return el
    def container_child(self, el, container):
        while el.getparent() is not container: el=el.getparent()
        return el
    def del_range(self, A, B):
        s, ps, offs = self.text()
        i,a=self.locate(A,ps,offs); j,b=self.locate(B,ps,offs)
        if i==j: self.del_chars(ps[i],a,b); return
        pi, pj = ps[i], ps[j]
        self.del_chars(pi, a, len(self.ptext(pi)))
        self.del_chars(pj, 0, b)
        # удалить всё между pi и pj на уровне общего контейнера
        anc_i=set(pi.iterancestors()); cont=next(x for x in pj.iterancestors() if x in anc_i)
        ci=self.container_child(pi,cont); cj=self.container_child(pj,cont)
        el=ci.getnext()
        while el is not None and el is not cj:
            nx=el.getnext(); cont.remove(el); el=nx
        self.touched.update([pi,pj])
    def find_one(self, pattern, flags=0):
        s,_,_=self.text(); m=list(re.finditer(pattern,s,flags)); assert len(m)==1,(pattern,len(m)); return m[0]
    def para_with(self, sub, n=1):
        hits=[p for p in self.paras() if sub in self.ptext(p)]; assert len(hits)==n,(sub,len(hits)); return hits
    # ---------- условия ----------
    def conditions(self, truth, skip=()):
        """Обрабатывает [[ЕСЛИ: …]] … [[КОНЕЦ]] от самых вложенных. truth: dict условие→bool."""
        while True:
            s,_,_=self.text()
            toks=[(m.start(),m.end(),m.group(1)) for m in re.finditer(r'\[\[(?:ЕСЛИ:\s*([^\]]+)|КОНЕЦ)\]\]',s)]
            stack=[]; pair=None
            for st,en,cond in toks:
                if cond is not None: stack.append((st,en,cond.strip()))
                else:
                    if not stack: raise ValueError('КОНЕЦ без ЕСЛИ @%d'%st)
                    o=stack.pop()
                    if o[2] in skip: continue
                    pair=(o,(st,en)); break
            if pair is None: break
            (os_,oe,cond),(cs,ce)=pair
            assert cond in truth, 'Неизвестное условие: '+cond
            if truth[cond]:
                self.del_range(cs,ce); self.del_range(os_,oe)
            else:
                self.del_range(os_,ce)
    def drop_empty_touched(self):
        for p in list(self.touched):
            if p.getparent() is None: continue
            par=p.getparent()
            if self.ptext(p).strip()=='' and p.find('.//'+q('drawing')) is None:
                # ⚠️ в ячейке таблицы должен остаться хотя бы один абзац
                if par.tag==q('tc') and len(par.findall(q('p')))==1: continue
                par.remove(p)
        self.touched=set()

    def tidy_spaces(self):
        """✂️ После удаления маркеров: убрать пробелы в начале/конце абзаца и двойные пробелы."""
        for p in self.ever:
            if p.getparent() is None: continue
            rs=self.truns(p)
            if not rs: continue
            for r in rs:
                t=r.find(q('t')); t.text=re.sub(r' {2,}',' ',t.text or '')
            # двойной пробел на стыке runs
            for r1,r2 in zip(rs,rs[1:]):
                t1,t2=r1.find(q('t')),r2.find(q('t'))
                if (t1.text or '').endswith(' ') and (t2.text or '').startswith(' '): t2.text=t2.text[1:]
            for r in rs:
                t=r.find(q('t'))
                if t.text: t.text=t.text.lstrip(); break
            for r in reversed(rs):
                t=r.find(q('t'))
                if t.text: t.text=t.text.rstrip(); break
            # пробел перед знаком препинания
            for r in rs:
                t=r.find(q('t')); t.text=re.sub(r' +([,.;:])',r'\1',t.text or '')
