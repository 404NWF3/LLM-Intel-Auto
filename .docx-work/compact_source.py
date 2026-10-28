import ast,io,tokenize,textwrap

def compact(data):
    lines=data.splitlines();tokens=list(tokenize.generate_tokens(io.StringIO(data).readline))
    safe={t.start[0] for t in tokens if t.type==tokenize.NL}
    blocked={t.start[0] for t in tokens if t.type==tokenize.COMMENT}
    for t in tokens:
        if t.type==tokenize.STRING and t.end[0]>t.start[0]:blocked.update(range(t.start[0],t.end[0]+1))
    out=[];i=0
    while i<len(lines):
        first=i+1;line=lines[i];end=i+1
        while line.strip() and end in safe and end not in blocked and end+1 not in blocked and end<len(lines):
            nxt=lines[end].strip()
            if not nxt:break
            candidate=line.rstrip()+' '+nxt
            if len(candidate)>74:break
            line=candidate;end+=1
        out.append((line,first,end));i=end
    result='\n'.join(r[0] for r in out)+'\n'
    assert ast.dump(ast.parse(result))==ast.dump(ast.parse(data))
    return out
